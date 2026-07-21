"""Auth routes — paths match monolith /api/v1/auth/*."""
from __future__ import annotations
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.controllers import auth as ctrl
from app.deps import CurrentUser, AsyncSessionDep
from app.schemas.auth import AdminConfirmEmailIn, AdminLoginIn, AdminOTPLoginIn, AdminRegisterIn, AdminResendConfirmIn, DeliveryLoginIn, ForgotPasswordIn, GoogleLoginIn, GuestIn, LogoutIn, MessageOut, ProfileUpdateIn, RefreshIn, ResetPasswordIn, RetailerGoogleFinishIn, RetailerGoogleIn, RetailerLoginIn, RetailerOtpVerifyIn, RetailerUploadBase64In, SendOTPIn, TokenOut, VerifyOTPIn
from app.services import auth as auth_svc
from package.common.errors import AppError
from app.controllers.auth_async import AuthController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await AuthController(session).call(fn, *args, **kwargs)

router = APIRouter(prefix='/auth', tags=['auth'])
_bearer = HTTPBearer(auto_error=False)

@router.post('/otp/send')
async def send_otp(body: SendOTPIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.send_otp, body.phone, body.purpose, str(body.email) if body.email else None)

@router.post('/otp/verify', response_model=TokenOut)
async def verify_otp(body: VerifyOTPIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.verify_otp, body.phone, body.code, body.name, str(body.email) if body.email else None, body.terms_accepted)

@router.post('/google', response_model=TokenOut)
async def google_login(body: GoogleLoginIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.google_login, body.id_token, body.terms_accepted)

@router.get('/google/setup')
def customer_google_setup(request: Request):
    return auth_svc.customer_google_oauth_setup(str(request.base_url).rstrip('/'))

@router.get('/google/start')
def customer_google_start(request: Request, app_redirect: str=Query(..., min_length=8)):
    api_base = str(request.base_url).rstrip('/')
    try:
        url = auth_svc.customer_google_oauth_authorize_url(api_base=api_base, app_redirect=app_redirect)
    except AppError as e:
        setup = auth_svc.customer_google_oauth_setup(api_base)
        return HTMLResponse(f"<html><body style='font-family:sans-serif;padding:24px;max-width:640px'><h3>Google sign-in not configured</h3><p>{e.detail}</p><p><b>Add this redirect URI in Google Cloud (Web client):</b><br><code>{setup['redirect_uri']}</code></p></body></html>", status_code=e.status_code)
    return RedirectResponse(url)

@router.get('/google/callback')
async def customer_google_callback(session: AsyncSessionDep, code: str | None=None, state: str | None=None, error: str | None=None):
    if error:
        return HTMLResponse(f'<html><body><p>Google sign-in cancelled: {error}</p></body></html>', status_code=400)
    if not code or not state:
        return HTMLResponse('<html><body><p>Missing Google code.</p></body></html>', status_code=400)
    try:
        redirect_to, _tokens = await _domain(session, auth_svc.customer_google_oauth_finish, code=code, state=state)
    except Exception as e:
        detail = getattr(e, 'detail', None) or str(e)
        return HTMLResponse(f"<html><body style='font-family:sans-serif;padding:24px'><h3>Google sign-in failed</h3><p>{detail}</p></body></html>", status_code=400)
    return RedirectResponse(redirect_to)

@router.post('/google/finish', response_model=TokenOut)
async def customer_google_finish(body: RetailerGoogleFinishIn, session: AsyncSessionDep):
    return auth_svc.retailer_google_oauth_exchange(body.code)

@router.post('/guest', response_model=TokenOut)
async def guest(body: GuestIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.guest_login)

@router.get('/admin/registration-status')
async def admin_registration_status(session: AsyncSessionDep):
    return await _domain(session, ctrl.admin_registration_status)

@router.post('/admin/register')
async def admin_register(body: AdminRegisterIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.admin_register, body.name, body.phone, str(body.email), body.password)

@router.post('/admin/confirm-email')
async def admin_confirm_email(body: AdminConfirmEmailIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.admin_confirm_email, str(body.email), body.code)

@router.post('/admin/resend-confirmation')
async def admin_resend_confirmation(body: AdminResendConfirmIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.admin_resend_confirmation, str(body.email))

@router.post('/admin/login', response_model=TokenOut)
async def admin_login(body: AdminLoginIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.admin_login, body.password, phone=body.phone, email=str(body.email) if body.email else None)

@router.post('/admin/otp', response_model=TokenOut)
async def admin_otp(body: AdminOTPLoginIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.admin_otp_login, body.phone, body.code)

@router.post('/delivery/login', response_model=TokenOut)
async def delivery_login(body: DeliveryLoginIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.delivery_login, body.phone, password=body.password, code=body.code)

@router.post('/retailer/upload')
async def retailer_register_upload(file: UploadFile=File(...), purpose: str=Form('kyc')):
    content = await file.read()
    return ctrl.retailer_upload(content, purpose, file.filename or 'upload.jpg', file.content_type)

@router.post('/retailer/upload-base64')
def retailer_register_upload_base64(body: RetailerUploadBase64In):
    return ctrl.retailer_upload_base64(body.content_base64, body.purpose, body.filename, body.content_type)

@router.post('/retailer/otp/verify', response_model=TokenOut)
async def retailer_otp_verify(body: RetailerOtpVerifyIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.retailer_otp_login, body.phone, body.code, body.name, body.terms_accepted)

@router.post('/retailer/google', response_model=TokenOut)
async def retailer_google(body: RetailerGoogleIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.retailer_google_login, body.id_token, body.terms_accepted)

@router.get('/retailer/google/setup')
def retailer_google_setup(request: Request):
    return auth_svc.retailer_google_oauth_setup(str(request.base_url).rstrip('/'))

@router.get('/retailer/google/start')
def retailer_google_start(
    request: Request,
    app_redirect: str = Query(..., min_length=8),
    format: str | None = Query(None, description="json = return authorize URL (for mobile WebBrowser)"),
):
    api_base = str(request.base_url).rstrip('/')
    try:
        url = auth_svc.retailer_google_oauth_authorize_url(api_base=api_base, app_redirect=app_redirect)
    except AppError as e:
        setup = auth_svc.retailer_google_oauth_setup(api_base)
        if (format or '').lower() == 'json':
            return JSONResponse(
                {"success": False, "detail": e.detail, "redirect_uri": setup.get("redirect_uri")},
                status_code=e.status_code,
            )
        return HTMLResponse(
            f"<html><body><h3>Google sign-in not configured</h3><p>{e.detail}</p>"
            f"<code>{setup['redirect_uri']}</code></body></html>",
            status_code=e.status_code,
        )
    if (format or '').lower() == 'json':
        return {
            "authorize_url": url,
            "redirect_uri": auth_svc.retailer_google_callback_uri(),
        }
    return RedirectResponse(url)

@router.get('/retailer/google/callback')
async def retailer_google_callback(session: AsyncSessionDep, code: str | None=None, state: str | None=None, error: str | None=None):
    if error:
        return HTMLResponse(f'<html><body><p>Google sign-in cancelled: {error}</p></body></html>', status_code=400)
    if not code or not state:
        return HTMLResponse('<html><body><p>Missing Google code.</p></body></html>', status_code=400)
    try:
        redirect_to, _tokens = await _domain(session, auth_svc.retailer_google_oauth_finish, code=code, state=state)
    except Exception as e:
        detail = getattr(e, 'detail', None) or str(e)
        return HTMLResponse(f'<html><body><h3>Google sign-in failed</h3><p>{detail}</p></body></html>', status_code=400)
    return RedirectResponse(redirect_to)

@router.post('/retailer/google/finish', response_model=TokenOut)
async def retailer_google_finish(body: RetailerGoogleFinishIn, session: AsyncSessionDep):
    return auth_svc.retailer_google_oauth_exchange(body.code)

@router.post('/retailer/login', response_model=TokenOut)
async def retailer_login(body: RetailerLoginIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.retailer_login, body.phone, password=body.password, code=body.code)

@router.post('/forgot-password')
async def forgot(body: ForgotPasswordIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.send_otp, body.phone, 'reset', None)

@router.post('/reset-password', response_model=MessageOut)
async def reset(body: ResetPasswordIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.reset_password, body.phone, body.code, body.new_password)

@router.post('/refresh', response_model=TokenOut)
async def refresh(body: RefreshIn, session: AsyncSessionDep):
    return await _domain(session, ctrl.refresh_tokens, body.refresh_token)

@router.post('/logout', response_model=MessageOut)
async def logout(body: LogoutIn, user: CurrentUser, session: AsyncSessionDep, credentials: HTTPAuthorizationCredentials | None=Depends(_bearer)):
    access = credentials.credentials if credentials else None
    return await _domain(session, ctrl.logout, user, access_token=access, refresh_token=body.refresh_token)

@router.get('/me')
def me(user: CurrentUser):
    return ctrl.me(user)

@router.patch('/me')
async def update_me(body: ProfileUpdateIn, user: CurrentUser, session: AsyncSessionDep):
    return await _domain(session, ctrl.update_me, user, body.model_dump(exclude_unset=True))
