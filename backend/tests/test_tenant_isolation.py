def test_design_contract():
 from app.models import Project,Target,Run
 assert all(hasattr(x,'tenant_id') for x in (Project,Target,Run))
