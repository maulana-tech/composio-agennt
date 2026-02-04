COMPOSIO_MANAGE_CONNECTIONS
{
  "toolkits": [
    "facebook"
  ],
  "reinitiate_all": false,
  "session_id": "rise"
}


COMPOSIO_MULTI_EXECUTE_TOOL
{
  "tools": [
    {
      "tool_slug": "FACEBOOK_LIST_MANAGED_PAGES",
      "arguments": {
        "user_id": "me",
        "limit": 25,
        "fields": "id,name,category,tasks,link"
      }
    }
  ],
  "sync_response_to_workbench": false,
  "session_id": "rise",
  "current_step": "FETCHING_PAGES",
  "current_step_metric": "0/1"
}

COMPOSIO_MULTI_EXECUTE_TOOL
{
  "tools": [
    {
      "tool_slug": "FACEBOOK_CREATE_POST",
      "arguments": {
        "page_id": "110434481320405",
        "message": "test",
        "published": true
      }
    }
  ],
  "sync_response_to_workbench": false,
  "session_id": "rise",
  "current_step": "CREATING_POST",
  "current_step_metric": "0/1"
}

COMPOSIO_GET_TOOL_SCHEMAS
{
  "tool_slugs": [
    "FACEBOOK_GET_POST"
  ],
  "session_id": "rise"
}


COMPOSIO_MULTI_EXECUTE_TOOL
{
  "tools": [
    {
      "tool_slug": "FACEBOOK_GET_POST",
      "arguments": {
        "post_id": "110434481320405_926268606404417",
        "fields": "id,message,created_time,permalink_url,from"
      }
    }
  ],
  "sync_response_to_workbench": false,
  "session_id": "rise",
  "current_step": "VERIFYING_POST",
  "current_step_metric": "0/1"
}