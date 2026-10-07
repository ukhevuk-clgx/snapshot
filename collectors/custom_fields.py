from collectors.base import PaginatedCollector
class CustomFieldsCollector(PaginatedCollector):
    entity_name='custom fields'
    endpoint='/rest/api/3/field/search'
    params={'type': 'custom', 'orderBy': 'name'}
    def map_item(self,i):return {"id":i.get("id"),"name":i.get("name"),"description":i.get("description"),"numericId":i.get("numericId"),"isLocked":i.get("isLocked"),"isManaged":i.get("isManaged"),"schemaCustom":(i.get("schema") or {}).get("custom"),"searcherKey":i.get("searcherKey")}
