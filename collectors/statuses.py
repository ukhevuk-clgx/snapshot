from collectors.base import PaginatedCollector
class StatusesCollector(PaginatedCollector):
    entity_name="statuses";endpoint="/rest/api/3/statuses/search"
    def map_item(self,i):
        c=i.get("statusCategory");s=i.get("scope") or {};p=s.get("project") or {}
        if isinstance(c,dict):cid,ck,cn=c.get("id"),c.get("key"),c.get("name")
        else:cid,ck,cn=None,c,c
        return {"id":i.get("id"),"name":i.get("name"),"description":i.get("description"),"statusCategoryId":cid,"statusCategoryKey":ck,"statusCategoryName":cn,"scopeType":s.get("type"),"scopeProjectId":p.get("id"),"scopeProjectKey":p.get("key")}
