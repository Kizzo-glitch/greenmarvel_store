

class TTClidCaptureMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Capture ttclid from URL if present
        ttclid = request.GET.get('ttclid')
        if ttclid:
            request.session['ttclid'] = ttclid
            # Also persist as a cookie (so it survives session expiry)
            response = self.get_response(request)
            response.set_cookie(
                'ttclid',
                ttclid,
                max_age=60 * 60 * 24 * 30,  # 30 days
                samesite='Lax',
                secure=request.is_secure(),
            )
            return response
        
        return self.get_response(request)