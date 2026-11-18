from pipelineguard.cloudflare import CloudflareBuilds

def test_classify_terminal_outcomes():
    assert CloudflareBuilds.classify({'status':'success','build_outcome':'success'})=='success'
    assert CloudflareBuilds.classify({'status':'failed','build_outcome':'failure'})=='failure'
    assert CloudflareBuilds.classify({'status':'cancelled'})=='cancelled'
    assert CloudflareBuilds.classify({'status':'running'})=='incomplete'

def test_completed_without_outcome_is_not_assumed_success():
    assert CloudflareBuilds.classify({'status':'completed'})=='incomplete'
