from collectors.base import PaginatedCollector
class ScreensCollector(PaginatedCollector):
    entity_name='screens'
    endpoint='/rest/api/3/screens'
    params={'orderBy': 'name'}
    def map_item(self,i):return {"id":i.get("id"),"name":i.get("name"),"description":i.get("description")}
