import requests
from collectors.base import BaseCollector
from utils.logger import Logger
class FieldSchemesCollector(BaseCollector):
 entity_name="field schemes"
 def collect(self):
  self.start()
  try:raw=self.client.get_paginated("/rest/api/3/config/fieldschemes")
  except requests.HTTPError as e:
   status=e.response.status_code if e.response is not None else None
   if status in {400,403,404}:Logger.warning(f"Field Schemes API unavailable (HTTP {status}); continuing with legacy data");return [],False
   raise
  rows=[{"id":x.get("id"),"name":x.get("name"),"description":x.get("description"),"fieldsCount":x.get("fieldsCount"),"isDefault":x.get("isDefault")} for x in raw];self.done(rows);return rows,True
