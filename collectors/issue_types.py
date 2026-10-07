from collectors.base import ListCollector
class IssueTypesCollector(ListCollector):
    entity_name='issue types'
    endpoint='/rest/api/3/issuetype'
    def map_item(self,i):return {"id":i.get("id"),"name":i.get("name"),"description":i.get("description"),"subtask":i.get("subtask"),"hierarchyLevel":i.get("hierarchyLevel")}
