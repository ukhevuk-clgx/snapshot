from collectors.base import PaginatedCollector
class IssueTypeScreenSchemesCollector(PaginatedCollector):
    entity_name='issue type screen schemes'
    endpoint='/rest/api/3/issuetypescreenscheme'
    params={'orderBy': 'name'}
    def map_item(self,i):return {"id":i.get("id"),"name":i.get("name"),"description":i.get("description"),"projectCount":(i.get("projects") or {}).get("total")}
