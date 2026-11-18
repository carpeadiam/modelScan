from pipelineguard.dataset import validate_records

def row(**kw):
    base={'cloudflare_build_uuid':'12345678-1234-1234-1234-123456789012','commit_sha':'abc','timestamp':'2026-01-01T00:00:00Z','actual_build_outcome':'success','actual_duration':42,'collection_status':'verified'}
    base.update(kw); return base

def test_accepts_verified_real_shaped_record():
    valid,rejected=validate_records([row()]); assert len(valid)==1 and not rejected

def test_rejects_duplicate_uuid():
    valid,rejected=validate_records([row(),row(execution_id='other')]); assert len(valid)==1 and rejected[0]['reason']=='duplicate_build_uuid'

def test_excludes_cancelled_and_unverified():
    valid,rejected=validate_records([row(actual_build_outcome='cancelled'),row(collection_status='incomplete')]); assert not valid and len(rejected)==2

def test_dataset_frame_has_binary_failure_label():
    from pipelineguard.dataset import records_to_frame
    record=row()
    record['features']={'changed_files':2}
    frame=records_to_frame([record])
    assert frame.iloc[0]['label']==0
    record['cloudflare_build_uuid']='87654321-4321-4321-4321-210987654321'
    record['actual_build_outcome']='failure'
    frame=records_to_frame([record])
    assert frame.iloc[0]['label']==1
