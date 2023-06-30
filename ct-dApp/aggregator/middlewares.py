def attach_middlewares(app):
    @app.on_response
    async def prevent_xss(request, response):
        """
        Prevent XSS attacks
        """
        response.headers["x-xss-protection"] = "1; mode=block"
