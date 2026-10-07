from collectors.base import PaginatedCollector
class WorkflowsCollector(PaginatedCollector):
    entity_name='workflows'
    endpoint='/rest/api/3/workflow/search'
    params={'expand': 'transitions'}
    def map_item(self,i):return {"id":i.get("id"),"name":i.get("name"),"description":i.get("description"),"isActive":i.get("isActive"),"isDefault":i.get("isDefault"),"hasDraftWorkflow":i.get("hasDraftWorkflow"),"transitionCount":len(i.get("transitions") or [])}
