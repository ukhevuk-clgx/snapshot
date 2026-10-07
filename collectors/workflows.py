from collectors.base import PaginatedCollector


def _transition_screen_ids(transitions):
    found = set()

    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("screenId", "screenID") and isinstance(item, (str, int)) and not isinstance(item, bool):
                    found.add(str(item))
                elif key == "screen" and isinstance(item, (str, int)) and not isinstance(item, bool):
                    found.add(str(item))
                elif key == "screen" and isinstance(item, dict):
                    screen_id = item.get("id")
                    if isinstance(screen_id, (str, int)) and not isinstance(screen_id, bool):
                        found.add(str(screen_id))
                    visit(item)
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(transitions)
    return sorted(found)


class WorkflowsCollector(PaginatedCollector):
    entity_name='workflows'
    endpoint='/rest/api/3/workflow/search'
    params={'expand': 'transitions'}
    def map_item(self,i):
        transitions=i.get("transitions") or []
        return {
            "id":i.get("id"),"name":i.get("name"),"description":i.get("description"),
            "isActive":i.get("isActive"),"isDefault":i.get("isDefault"),
            "hasDraftWorkflow":i.get("hasDraftWorkflow"),"transitionCount":len(transitions),
            "transitionScreenIds":_transition_screen_ids(transitions),
        }
