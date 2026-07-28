# Plugin SDK (Draft)

This document will describe the plugin interface, discovery, and lifecycle.

Plugin API (sketch):

class Plugin:
    name = "example"

    def can_handle(self, request):
        ...

    async def execute(self, request, context):
        ...

Plugins live in `backend/plugins/` and can be loaded by the AuraService.
