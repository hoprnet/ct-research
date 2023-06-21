def setup_middlewares(app):
    @app.on_response
    async def prevent_xss(request, response):
        response.headers["x-xss-protection"] = "1; mode=block"
