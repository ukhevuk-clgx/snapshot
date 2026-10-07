from collectors.base import BaseCollector
class NotificationSchemesCollector(BaseCollector):
 entity_name="notification schemes"
 def collect(self):
  self.start();raw=self.client.get_paginated("/rest/api/3/notificationscheme",params={"expand":"all"});rows=[];events=[]
  for s in raw:
   es=s.get("notificationSchemeEvents") or [];rows.append({"id":s.get("id"),"name":s.get("name"),"description":s.get("description"),"eventCount":len(es)})
   for e in es:
    ev=e.get("event") or {}
    for n in e.get("notifications") or []:events.append({"notificationSchemeId":s.get("id"),"notificationSchemeName":s.get("name"),"eventId":ev.get("id"),"eventName":ev.get("name"),"notificationId":n.get("id"),"recipientType":n.get("notificationType"),"parameter":n.get("parameter")})
  self.done(rows);return rows,events
