export interface Env {
  DB: D1Database;
  RAW_BUILDS: R2Bucket;
  ASSETS: Fetcher;
  PIPELINEGUARD_API_KEY: string;
}

type Json = Record<string, any>;
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*' } });
const auth = (req: Request, env: Env) => req.headers.get('authorization') === `Bearer ${env.PIPELINEGUARD_API_KEY}`;
const safeParse = (v: string | null) => { try { return v ? JSON.parse(v) : null; } catch { return null; } };

async function listBuilds(env: Env, limit: number) {
  const result = await env.DB.prepare('SELECT * FROM executions ORDER BY timestamp DESC LIMIT ?').bind(Math.min(Math.max(limit, 1), 1000)).all();
  return (result.results || []).map((r: any) => ({ ...r, features: safeParse(r.features_json), features_json: undefined }));
}

function infer(model: Json, features: Json) {
  const names: string[] = model.feature_names;
  const x = names.map((name: string, i: number) => {
    const raw = Number(features[name]);
    const value = Number.isFinite(raw) ? raw : model.imputer_medians[i];
    return (value - model.scaler_mean[i]) / (model.scaler_scale[i] || 1);
  });
  let total = 0;
  for (const tree of model.trees) {
    let node = 0;
    while (tree.children_left[node] !== tree.children_right[node]) {
      const f = tree.feature[node];
      node = x[f] <= tree.threshold[node] ? tree.children_left[node] : tree.children_right[node];
    }
    const counts = tree.value[node];
    const sum = counts.reduce((a: number, b: number) => a + b, 0) || 1;
    total += counts[1] / sum;
  }
  const probability = total / model.trees.length;
  return { probability, label: probability >= (model.threshold ?? 0.5) ? 1 : 0, model_status: 'trained' };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (request.method === 'OPTIONS') return new Response(null, { headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'authorization,content-type', 'access-control-allow-methods': 'GET,POST,OPTIONS' } });
    if (url.pathname.startsWith('/api/')) {
      if (url.pathname === '/api/health' && request.method === 'GET') {
        const model = await env.RAW_BUILDS.get('models/model.json');
        return json({ status: 'ok', model_status: model ? 'trained' : 'Model not trained: insufficient real execution history.' });
      }
      if (url.pathname === '/api/summary' && request.method === 'GET') {
        const rows = await env.DB.prepare("SELECT COUNT(*) total, SUM(CASE WHEN actual_build_outcome='success' THEN 1 ELSE 0 END) successes, SUM(CASE WHEN actual_build_outcome='failure' THEN 1 ELSE 0 END) failures, MAX(timestamp) last_execution FROM executions WHERE collection_status='verified'").first<any>();
        const total = Number(rows?.total || 0), failures = Number(rows?.failures || 0);
        return json({ total, successes: Number(rows?.successes || 0), failures, failure_rate: total ? failures / total : null, last_execution: rows?.last_execution || null });
      }
      if (url.pathname === '/api/builds' && request.method === 'GET') return json({ builds: await listBuilds(env, Number(url.searchParams.get('limit') || 100)) });
      if (url.pathname === '/api/model' && request.method === 'GET') {
        const obj = await env.RAW_BUILDS.get('models/evaluation.json');
        return json(obj ? await obj.json() : { model_status: 'Model not trained: insufficient real execution history.' });
      }
      if (url.pathname === '/api/predictions' && request.method === 'POST') {
        if (!auth(request, env)) return json({ error: 'Unauthorized' }, 401);
        const r = await request.json() as Json;
        if (!r.execution_id || !r.commit_sha || !r.branch || !r.timestamp || !r.features) return json({ error: 'Missing pre-build prediction fields' }, 400);
        await env.DB.prepare('INSERT INTO predictions (execution_id,commit_sha,branch,timestamp,features_json,prediction_probability,predicted_label,model_status) VALUES (?,?,?,?,?,?,?,?)')
          .bind(r.execution_id,r.commit_sha,r.branch,r.timestamp,JSON.stringify(r.features),r.probability ?? null,r.label ?? null,r.model_status || 'unknown').run();
        return json({ recorded: true, execution_id: r.execution_id }, 201);
      }
      if (url.pathname === '/api/ingest' && request.method === 'POST') {
        if (!auth(request, env)) return json({ error: 'Unauthorized' }, 401);
        const r = await request.json() as Json;
        const required = ['execution_id','cloudflare_build_uuid','commit_sha','branch','timestamp','features','actual_build_outcome','collection_status'];
        if (required.some(k => r[k] === undefined || r[k] === null)) return json({ error: 'Missing required execution fields' }, 400);
        if (!/^[0-9a-f-]{20,}$/i.test(String(r.cloudflare_build_uuid))) return json({ error: 'Invalid Cloudflare build UUID' }, 400);
        const existing = await env.DB.prepare('SELECT cloudflare_build_uuid FROM executions WHERE cloudflare_build_uuid = ?').bind(r.cloudflare_build_uuid).first();
        if (existing) return json({ error: 'Duplicate Cloudflare build UUID' }, 409);
        const key = `executions/${r.cloudflare_build_uuid}.json`;
        const raw = { build: r.raw_build || null, logs: r.raw_logs || null, collected_at: new Date().toISOString() };
        await env.RAW_BUILDS.put(key, JSON.stringify(raw), { httpMetadata: { contentType: 'application/json' } });
        try {
          await env.DB.prepare(`INSERT INTO executions (execution_id,cloudflare_build_uuid,commit_sha,branch,timestamp,features_json,prediction_probability,predicted_label,actual_build_status,actual_build_outcome,actual_duration,experiment_scenario,collection_status,raw_object_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)`)
            .bind(r.execution_id,r.cloudflare_build_uuid,r.commit_sha,r.branch,r.timestamp,JSON.stringify(r.features),r.prediction_probability ?? null,r.predicted_label ?? null,r.actual_build_status ?? null,r.actual_build_outcome,r.actual_duration ?? null,r.experiment_scenario ?? null,r.collection_status,key).run();
        } catch (e) { return json({ error: 'D1 insert failed; raw object retained for reconciliation', detail: String(e) }, 409); }
        return json({ stored: true, cloudflare_build_uuid: r.cloudflare_build_uuid }, 201);
      }
      if (url.pathname === '/api/predict' && request.method === 'POST') {
        if (!auth(request, env)) return json({ error: 'Unauthorized' }, 401);
        const body = await request.json() as Json;
        const obj = await env.RAW_BUILDS.get('models/model.json');
        if (!obj) return json({ probability: null, label: null, model_status: 'Model not trained: insufficient real execution history.' });
        return json(infer(await obj.json<Json>(), body.features || {}));
      }
      if (url.pathname === '/api/model/upload' && request.method === 'POST') {
        if (!auth(request, env)) return json({ error: 'Unauthorized' }, 401);
        const body = await request.json() as Json;
        if (!body.model || !body.evaluation) return json({ error: 'model and evaluation required' }, 400);
        await env.RAW_BUILDS.put('models/model.json', JSON.stringify(body.model));
        await env.RAW_BUILDS.put('models/evaluation.json', JSON.stringify(body.evaluation));
        return json({ uploaded: true });
      }
      return json({ error: 'Not found' }, 404);
    }
    return env.ASSETS.fetch(request);
  }
};
