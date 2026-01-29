from composio.client.enums import Action
for a in Action:
    if "GMAIL" in a.name:
        print(a.name, a.slug)
