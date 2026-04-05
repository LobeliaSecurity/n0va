import app.server
import n0va


@app.server.service.onGet("/GetTest.get")
async def GetTest(ctx: n0va.RequestContext) -> n0va.HttpResponse:
    return n0va.HttpResponse(
        status=200,
        body=b"GET:" + ctx.request.content,
        content_type=b"text/html",
    )


@app.server.service.route("/PostTest.get", methods=("POST",))
async def PostTest(ctx: n0va.RequestContext) -> n0va.HttpResponse:
    return n0va.HttpResponse(
        status=200,
        body=b"POST:" + ctx.request.content,
        content_type=b"text/html",
    )
