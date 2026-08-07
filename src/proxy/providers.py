from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.server.auth import AuthProvider
from fastmcp.server.auth.providers.auth0 import Auth0Provider
from fastmcp.server.auth.providers.aws import AWSCognitoProvider
from fastmcp.server.auth.providers.azure import AzureProvider
from fastmcp.server.auth.providers.descope import DescopeProvider
from fastmcp.server.auth.providers.discord import DiscordProvider
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.providers.huggingface import HuggingFaceProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.auth.providers.keycloak import KeycloakAuthProvider
from fastmcp.server.auth.providers.oci import OCIProvider
from fastmcp.server.auth.providers.propelauth import (
    PropelAuthProvider,
    PropelAuthTokenIntrospectionOverrides,
)
from fastmcp.server.auth.providers.scalekit import ScalekitProvider
from fastmcp.server.auth.providers.supabase import SupabaseProvider
from fastmcp.server.auth.providers.workos import AuthKitProvider, WorkOSProvider
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    model_validator,
)

ConsentMode = bool | Literal["remember", "external"]


class AuthProviderLoadError(ValueError):
    """Raised when a validated FastMCP provider cannot be constructed."""


class _AuthProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def build(self, *, base_url: str) -> AuthProvider:
        raise NotImplementedError


class _RemoteAuthProviderConfig(_AuthProviderConfig):
    required_scopes: list[str] | None = None
    scopes_supported: list[str] | None = None
    resource_name: str | None = None
    resource_documentation: AnyHttpUrl | None = None


class _OAuthProxyCommonConfig(_AuthProviderConfig):
    resource_base_url: AnyHttpUrl | None = None
    issuer_url: AnyHttpUrl | None = None
    allowed_client_redirect_uris: list[str] | None = None
    jwt_signing_key: SecretStr | None = None
    require_authorization_consent: ConsentMode = True
    consent_csp_policy: str | None = None
    forward_resource: bool = True
    fallback_refresh_token_expiry_seconds: int | None = Field(default=None, gt=0)
    fastmcp_access_token_expiry_seconds: int | None = Field(default=None, gt=0)
    token_expiry_threshold_seconds: int = Field(default=0, ge=0)

    @property
    def jwt_signing_key_value(self) -> str | None:
        return self.jwt_signing_key.get_secret_value() if self.jwt_signing_key else None


class _OAuthProxyAuthProviderConfig(_OAuthProxyCommonConfig):
    required_scopes: list[str] | None = None


class Auth0AuthProviderConfig(_OAuthProxyAuthProviderConfig):
    provider: Literal["auth0"]
    config_url: AnyHttpUrl
    client_id: str
    client_secret: SecretStr
    audience: str
    timeout_seconds: int | None = Field(default=10, gt=0)
    redirect_path: str | None = None

    def build(self, *, base_url: str) -> AuthProvider:
        return Auth0Provider(
            config_url=self.config_url,
            client_id=self.client_id,
            client_secret=self.client_secret.get_secret_value(),
            audience=self.audience,
            timeout_seconds=self.timeout_seconds,
            base_url=base_url,
            resource_base_url=self.resource_base_url,
            issuer_url=self.issuer_url,
            required_scopes=self.required_scopes,
            redirect_path=self.redirect_path,
            allowed_client_redirect_uris=self.allowed_client_redirect_uris,
            jwt_signing_key=self.jwt_signing_key_value,
            require_authorization_consent=self.require_authorization_consent,
            consent_csp_policy=self.consent_csp_policy,
            forward_resource=self.forward_resource,
            fallback_refresh_token_expiry_seconds=(
                self.fallback_refresh_token_expiry_seconds
            ),
            fastmcp_access_token_expiry_seconds=(
                self.fastmcp_access_token_expiry_seconds
            ),
            token_expiry_threshold_seconds=self.token_expiry_threshold_seconds,
        )


class AwsCognitoAuthProviderConfig(_OAuthProxyAuthProviderConfig):
    provider: Literal["aws-cognito"]
    user_pool_id: str
    client_id: str
    client_secret: SecretStr
    timeout_seconds: int | None = Field(default=10, gt=0)
    aws_region: str = "eu-central-1"
    redirect_path: str = "/auth/callback"

    def build(self, *, base_url: str) -> AuthProvider:
        return AWSCognitoProvider(
            user_pool_id=self.user_pool_id,
            client_id=self.client_id,
            client_secret=self.client_secret.get_secret_value(),
            timeout_seconds=self.timeout_seconds,
            base_url=base_url,
            resource_base_url=self.resource_base_url,
            aws_region=self.aws_region,
            issuer_url=self.issuer_url,
            redirect_path=self.redirect_path,
            required_scopes=self.required_scopes,
            allowed_client_redirect_uris=self.allowed_client_redirect_uris,
            jwt_signing_key=self.jwt_signing_key_value,
            require_authorization_consent=self.require_authorization_consent,
            consent_csp_policy=self.consent_csp_policy,
            forward_resource=self.forward_resource,
            fallback_refresh_token_expiry_seconds=(
                self.fallback_refresh_token_expiry_seconds
            ),
            fastmcp_access_token_expiry_seconds=(
                self.fastmcp_access_token_expiry_seconds
            ),
            token_expiry_threshold_seconds=self.token_expiry_threshold_seconds,
        )


class AzureAuthProviderConfig(_OAuthProxyCommonConfig):
    provider: Literal["azure"]
    client_id: str
    client_secret: SecretStr | None = None
    tenant_id: str
    required_scopes: list[str]
    identifier_uri: str | None = None
    additional_authorize_scopes: list[str] | None = None
    base_authority: str = "login.microsoftonline.com"
    token_issuer: str | None = None
    enable_cimd: bool = True
    redirect_path: str | None = None

    @model_validator(mode="after")
    def validate_signing_credentials(self) -> AzureAuthProviderConfig:
        if self.client_secret is None and self.jwt_signing_key is None:
            raise ValueError("Azure requires client_secret or jwt_signing_key.")
        return self

    def build(self, *, base_url: str) -> AuthProvider:
        return AzureProvider(
            client_id=self.client_id,
            client_secret=(
                self.client_secret.get_secret_value() if self.client_secret else None
            ),
            tenant_id=self.tenant_id,
            required_scopes=self.required_scopes,
            base_url=base_url,
            resource_base_url=self.resource_base_url,
            identifier_uri=self.identifier_uri,
            issuer_url=str(self.issuer_url) if self.issuer_url else None,
            redirect_path=self.redirect_path,
            additional_authorize_scopes=self.additional_authorize_scopes,
            allowed_client_redirect_uris=self.allowed_client_redirect_uris,
            jwt_signing_key=self.jwt_signing_key_value,
            require_authorization_consent=self.require_authorization_consent,
            consent_csp_policy=self.consent_csp_policy,
            forward_resource=self.forward_resource,
            fallback_refresh_token_expiry_seconds=(
                self.fallback_refresh_token_expiry_seconds
            ),
            fastmcp_access_token_expiry_seconds=(
                self.fastmcp_access_token_expiry_seconds
            ),
            token_expiry_threshold_seconds=self.token_expiry_threshold_seconds,
            base_authority=self.base_authority,
            token_issuer=self.token_issuer,
            enable_cimd=self.enable_cimd,
        )


class DescopeAuthProviderConfig(_RemoteAuthProviderConfig):
    provider: Literal["descope"]
    config_url: AnyHttpUrl | None = None
    project_id: str | None = None
    descope_base_url: AnyHttpUrl | None = None

    @model_validator(mode="after")
    def validate_endpoint(self) -> DescopeAuthProviderConfig:
        if self.config_url is None and (
            self.project_id is None or self.descope_base_url is None
        ):
            raise ValueError(
                "Descope requires config_url or both project_id and descope_base_url."
            )
        return self

    def build(self, *, base_url: str) -> AuthProvider:
        return DescopeProvider(
            base_url=base_url,
            config_url=self.config_url,
            project_id=self.project_id,
            descope_base_url=self.descope_base_url,
            required_scopes=self.required_scopes,
            scopes_supported=self.scopes_supported,
            resource_name=self.resource_name,
            resource_documentation=self.resource_documentation,
        )


class DiscordAuthProviderConfig(_OAuthProxyAuthProviderConfig):
    provider: Literal["discord"]
    client_id: str
    client_secret: SecretStr
    timeout_seconds: int = Field(default=10, gt=0)
    enable_cimd: bool = True
    redirect_path: str | None = None

    def build(self, *, base_url: str) -> AuthProvider:
        return DiscordProvider(
            client_id=self.client_id,
            client_secret=self.client_secret.get_secret_value(),
            base_url=base_url,
            resource_base_url=self.resource_base_url,
            issuer_url=self.issuer_url,
            redirect_path=self.redirect_path,
            required_scopes=self.required_scopes,
            timeout_seconds=self.timeout_seconds,
            allowed_client_redirect_uris=self.allowed_client_redirect_uris,
            jwt_signing_key=self.jwt_signing_key_value,
            require_authorization_consent=self.require_authorization_consent,
            consent_csp_policy=self.consent_csp_policy,
            forward_resource=self.forward_resource,
            fallback_refresh_token_expiry_seconds=(
                self.fallback_refresh_token_expiry_seconds
            ),
            fastmcp_access_token_expiry_seconds=(
                self.fastmcp_access_token_expiry_seconds
            ),
            token_expiry_threshold_seconds=self.token_expiry_threshold_seconds,
            enable_cimd=self.enable_cimd,
        )


class GitHubAuthProviderConfig(_OAuthProxyAuthProviderConfig):
    provider: Literal["github"]
    client_id: str
    client_secret: SecretStr
    timeout_seconds: int = Field(default=10, gt=0)
    cache_ttl_seconds: int | None = Field(default=None, ge=0)
    max_cache_size: int | None = Field(default=None, gt=0)
    enable_cimd: bool = True
    redirect_path: str | None = None

    def build(self, *, base_url: str) -> AuthProvider:
        return GitHubProvider(
            client_id=self.client_id,
            client_secret=self.client_secret.get_secret_value(),
            base_url=base_url,
            resource_base_url=self.resource_base_url,
            issuer_url=self.issuer_url,
            redirect_path=self.redirect_path,
            required_scopes=self.required_scopes,
            timeout_seconds=self.timeout_seconds,
            cache_ttl_seconds=self.cache_ttl_seconds,
            max_cache_size=self.max_cache_size,
            allowed_client_redirect_uris=self.allowed_client_redirect_uris,
            jwt_signing_key=self.jwt_signing_key_value,
            require_authorization_consent=self.require_authorization_consent,
            consent_csp_policy=self.consent_csp_policy,
            forward_resource=self.forward_resource,
            fallback_refresh_token_expiry_seconds=(
                self.fallback_refresh_token_expiry_seconds
            ),
            fastmcp_access_token_expiry_seconds=(
                self.fastmcp_access_token_expiry_seconds
            ),
            token_expiry_threshold_seconds=self.token_expiry_threshold_seconds,
            enable_cimd=self.enable_cimd,
        )


class GoogleAuthProviderConfig(_OAuthProxyAuthProviderConfig):
    provider: Literal["google"]
    client_id: str
    client_secret: SecretStr | None = None
    valid_scopes: list[str] | None = None
    timeout_seconds: int = Field(default=10, gt=0)
    extra_authorize_params: dict[str, str] | None = None
    enable_cimd: bool = True
    redirect_path: str | None = None

    @model_validator(mode="after")
    def validate_signing_credentials(self) -> GoogleAuthProviderConfig:
        if self.client_secret is None and self.jwt_signing_key is None:
            raise ValueError("Google requires client_secret or jwt_signing_key.")
        return self

    def build(self, *, base_url: str) -> AuthProvider:
        return GoogleProvider(
            client_id=self.client_id,
            client_secret=(
                self.client_secret.get_secret_value() if self.client_secret else None
            ),
            base_url=base_url,
            resource_base_url=self.resource_base_url,
            issuer_url=self.issuer_url,
            redirect_path=self.redirect_path,
            required_scopes=self.required_scopes,
            valid_scopes=self.valid_scopes,
            timeout_seconds=self.timeout_seconds,
            allowed_client_redirect_uris=self.allowed_client_redirect_uris,
            jwt_signing_key=self.jwt_signing_key_value,
            require_authorization_consent=self.require_authorization_consent,
            consent_csp_policy=self.consent_csp_policy,
            forward_resource=self.forward_resource,
            fallback_refresh_token_expiry_seconds=(
                self.fallback_refresh_token_expiry_seconds
            ),
            fastmcp_access_token_expiry_seconds=(
                self.fastmcp_access_token_expiry_seconds
            ),
            token_expiry_threshold_seconds=self.token_expiry_threshold_seconds,
            extra_authorize_params=self.extra_authorize_params,
            enable_cimd=self.enable_cimd,
        )


class HuggingFaceAuthProviderConfig(_OAuthProxyAuthProviderConfig):
    provider: Literal["huggingface"]
    client_id: str
    client_secret: SecretStr | None = None
    valid_scopes: list[str] | None = None
    timeout_seconds: int = Field(default=10, gt=0)
    extra_authorize_params: dict[str, str] | None = None
    extra_token_params: dict[str, str] | None = None
    enable_cimd: bool = True
    redirect_path: str | None = None

    @model_validator(mode="after")
    def validate_signing_credentials(self) -> HuggingFaceAuthProviderConfig:
        if self.client_secret is None and self.jwt_signing_key is None:
            raise ValueError("Hugging Face requires client_secret or jwt_signing_key.")
        return self

    def build(self, *, base_url: str) -> AuthProvider:
        return HuggingFaceProvider(
            client_id=self.client_id,
            client_secret=(
                self.client_secret.get_secret_value() if self.client_secret else None
            ),
            base_url=base_url,
            resource_base_url=self.resource_base_url,
            issuer_url=self.issuer_url,
            redirect_path=self.redirect_path,
            required_scopes=self.required_scopes,
            valid_scopes=self.valid_scopes,
            timeout_seconds=self.timeout_seconds,
            allowed_client_redirect_uris=self.allowed_client_redirect_uris,
            jwt_signing_key=self.jwt_signing_key_value,
            require_authorization_consent=self.require_authorization_consent,
            consent_csp_policy=self.consent_csp_policy,
            forward_resource=self.forward_resource,
            fallback_refresh_token_expiry_seconds=(
                self.fallback_refresh_token_expiry_seconds
            ),
            fastmcp_access_token_expiry_seconds=(
                self.fastmcp_access_token_expiry_seconds
            ),
            token_expiry_threshold_seconds=self.token_expiry_threshold_seconds,
            extra_authorize_params=self.extra_authorize_params,
            extra_token_params=self.extra_token_params,
            enable_cimd=self.enable_cimd,
        )


class KeycloakAuthProviderConfig(_AuthProviderConfig):
    provider: Literal["keycloak"]
    realm_url: AnyHttpUrl
    required_scopes: list[str] | None = None
    audience: str | list[str] | None = None

    def build(self, *, base_url: str) -> AuthProvider:
        return KeycloakAuthProvider(
            realm_url=self.realm_url,
            base_url=base_url,
            required_scopes=self.required_scopes,
            audience=self.audience,
        )


class OciAuthProviderConfig(_OAuthProxyAuthProviderConfig):
    provider: Literal["oci"]
    config_url: AnyHttpUrl
    client_id: str
    client_secret: SecretStr
    audience: str | None = None
    timeout_seconds: int | None = Field(default=10, gt=0)
    redirect_path: str | None = None

    def build(self, *, base_url: str) -> AuthProvider:
        return OCIProvider(
            config_url=self.config_url,
            client_id=self.client_id,
            client_secret=self.client_secret.get_secret_value(),
            timeout_seconds=self.timeout_seconds,
            base_url=base_url,
            resource_base_url=self.resource_base_url,
            audience=self.audience,
            issuer_url=self.issuer_url,
            required_scopes=self.required_scopes,
            redirect_path=self.redirect_path,
            allowed_client_redirect_uris=self.allowed_client_redirect_uris,
            jwt_signing_key=self.jwt_signing_key_value,
            require_authorization_consent=self.require_authorization_consent,
            consent_csp_policy=self.consent_csp_policy,
            forward_resource=self.forward_resource,
            fallback_refresh_token_expiry_seconds=(
                self.fallback_refresh_token_expiry_seconds
            ),
            fastmcp_access_token_expiry_seconds=(
                self.fastmcp_access_token_expiry_seconds
            ),
            token_expiry_threshold_seconds=self.token_expiry_threshold_seconds,
        )


class PropelAuthIntrospectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_seconds: int | None = Field(default=None, gt=0)
    cache_ttl_seconds: int | None = Field(default=None, ge=0)
    max_cache_size: int | None = Field(default=None, gt=0)

    def as_fastmcp_overrides(self) -> PropelAuthTokenIntrospectionOverrides:
        overrides: PropelAuthTokenIntrospectionOverrides = {}
        if self.timeout_seconds is not None:
            overrides["timeout_seconds"] = self.timeout_seconds
        if self.cache_ttl_seconds is not None:
            overrides["cache_ttl_seconds"] = self.cache_ttl_seconds
        if self.max_cache_size is not None:
            overrides["max_cache_size"] = self.max_cache_size
        return overrides


class PropelAuthProviderConfig(_RemoteAuthProviderConfig):
    provider: Literal["propelauth"]
    auth_url: AnyHttpUrl
    introspection_client_id: str
    introspection_client_secret: SecretStr
    resource: AnyHttpUrl | None = None
    token_introspection: PropelAuthIntrospectionConfig | None = None

    def build(self, *, base_url: str) -> AuthProvider:
        return PropelAuthProvider(
            auth_url=self.auth_url,
            introspection_client_id=self.introspection_client_id,
            introspection_client_secret=(
                self.introspection_client_secret.get_secret_value()
            ),
            base_url=base_url,
            required_scopes=self.required_scopes,
            scopes_supported=self.scopes_supported,
            resource_name=self.resource_name,
            resource_documentation=self.resource_documentation,
            resource=self.resource,
            token_introspection_overrides=(
                self.token_introspection.as_fastmcp_overrides()
                if self.token_introspection
                else None
            ),
        )


class ScalekitAuthProviderConfig(_RemoteAuthProviderConfig):
    provider: Literal["scalekit"]
    environment_url: AnyHttpUrl
    resource_id: str

    def build(self, *, base_url: str) -> AuthProvider:
        return ScalekitProvider(
            environment_url=self.environment_url,
            resource_id=self.resource_id,
            base_url=base_url,
            required_scopes=self.required_scopes,
            scopes_supported=self.scopes_supported,
            resource_name=self.resource_name,
            resource_documentation=self.resource_documentation,
        )


class SupabaseAuthProviderConfig(_RemoteAuthProviderConfig):
    provider: Literal["supabase"]
    project_url: AnyHttpUrl
    auth_route: str = "/auth/v1"
    algorithm: Literal["RS256", "ES256"] = "ES256"

    def build(self, *, base_url: str) -> AuthProvider:
        return SupabaseProvider(
            project_url=self.project_url,
            base_url=base_url,
            auth_route=self.auth_route,
            algorithm=self.algorithm,
            required_scopes=self.required_scopes,
            scopes_supported=self.scopes_supported,
            resource_name=self.resource_name,
            resource_documentation=self.resource_documentation,
        )


class AuthKitAuthProviderConfig(_RemoteAuthProviderConfig):
    provider: Literal["authkit"]
    authkit_domain: AnyHttpUrl
    resource_base_url: AnyHttpUrl | None = None

    def build(self, *, base_url: str) -> AuthProvider:
        return AuthKitProvider(
            authkit_domain=self.authkit_domain,
            base_url=base_url,
            resource_base_url=self.resource_base_url,
            required_scopes=self.required_scopes,
            scopes_supported=self.scopes_supported,
            resource_name=self.resource_name,
            resource_documentation=self.resource_documentation,
        )


class WorkOsAuthProviderConfig(_OAuthProxyAuthProviderConfig):
    provider: Literal["workos"]
    client_id: str
    client_secret: SecretStr
    authkit_domain: AnyHttpUrl
    valid_scopes: list[str] | None = None
    timeout_seconds: int = Field(default=10, gt=0)
    extra_authorize_params: dict[str, str] | None = None
    enable_cimd: bool = True
    redirect_path: str | None = None

    def build(self, *, base_url: str) -> AuthProvider:
        return WorkOSProvider(
            client_id=self.client_id,
            client_secret=self.client_secret.get_secret_value(),
            authkit_domain=str(self.authkit_domain),
            base_url=base_url,
            resource_base_url=self.resource_base_url,
            issuer_url=self.issuer_url,
            redirect_path=self.redirect_path,
            required_scopes=self.required_scopes,
            valid_scopes=self.valid_scopes,
            timeout_seconds=self.timeout_seconds,
            allowed_client_redirect_uris=self.allowed_client_redirect_uris,
            jwt_signing_key=self.jwt_signing_key_value,
            require_authorization_consent=self.require_authorization_consent,
            consent_csp_policy=self.consent_csp_policy,
            forward_resource=self.forward_resource,
            fallback_refresh_token_expiry_seconds=(
                self.fallback_refresh_token_expiry_seconds
            ),
            fastmcp_access_token_expiry_seconds=(
                self.fastmcp_access_token_expiry_seconds
            ),
            token_expiry_threshold_seconds=self.token_expiry_threshold_seconds,
            extra_authorize_params=self.extra_authorize_params,
            enable_cimd=self.enable_cimd,
        )


class JwtAuthProviderConfig(_AuthProviderConfig):
    provider: Literal["jwt"]
    public_key: str | None = None
    jwks_uri: AnyHttpUrl | None = None
    issuer: str | list[str] | None = None
    audience: str | list[str] | None = None
    algorithm: str | None = None
    required_scopes: list[str] | None = None
    ssrf_safe: bool = False

    @model_validator(mode="after")
    def validate_key_source(self) -> JwtAuthProviderConfig:
        if self.public_key is None and self.jwks_uri is None:
            raise ValueError("JWT authentication requires public_key or jwks_uri.")
        return self

    def build(self, *, base_url: str) -> AuthProvider:
        return JWTVerifier(
            public_key=self.public_key,
            jwks_uri=str(self.jwks_uri) if self.jwks_uri else None,
            issuer=self.issuer,
            audience=self.audience,
            algorithm=self.algorithm,
            required_scopes=self.required_scopes,
            base_url=base_url,
            ssrf_safe=self.ssrf_safe,
        )


AuthProviderConfig = Annotated[
    Auth0AuthProviderConfig
    | AuthKitAuthProviderConfig
    | AwsCognitoAuthProviderConfig
    | AzureAuthProviderConfig
    | DescopeAuthProviderConfig
    | DiscordAuthProviderConfig
    | GitHubAuthProviderConfig
    | GoogleAuthProviderConfig
    | HuggingFaceAuthProviderConfig
    | JwtAuthProviderConfig
    | KeycloakAuthProviderConfig
    | OciAuthProviderConfig
    | PropelAuthProviderConfig
    | ScalekitAuthProviderConfig
    | SupabaseAuthProviderConfig
    | WorkOsAuthProviderConfig,
    Field(discriminator="provider"),
]


def load_auth_provider(config: AuthProviderConfig, *, base_url: str) -> AuthProvider:
    """Construct a FastMCP provider from a fully validated typed configuration."""

    try:
        return config.build(base_url=base_url)
    except Exception as error:
        raise AuthProviderLoadError(
            f"Could not construct '{config.provider}' auth provider: {error}"
        ) from error
