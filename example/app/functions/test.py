import app.server


@app.server.service.onGet("/GetTest.get")
async def GetTest(connection, Request, ReplyHeader):
    ReplyHeader["ReplyContent"] = b"GET:" + Request["content"]
    ReplyHeader["Content-Type"] = b"text/html"
    ReplyHeader["Status"] = 200
    return ReplyHeader


@app.server.service.onPost("/PostTest.get")
async def PostTest(connection, Request, ReplyHeader):
    ReplyHeader["ReplyContent"] = b"POST:" + Request["content"]
    ReplyHeader["Content-Type"] = b"text/html"
    ReplyHeader["Status"] = 200
    return ReplyHeader
