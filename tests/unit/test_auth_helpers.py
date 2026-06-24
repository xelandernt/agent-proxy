from proxy.auth.challenge import build_auth_challenge
from proxy.auth.models import (
    audiences_match_resource,
    extract_audiences,
    extract_scopes,
    find_jwk,
    normalize_resource_uri,
    optional_string,
    principal_subject,
)


class TestOptionalString:
    def test_none_returns_none(self):
        assert optional_string(None) is None

    def test_empty_string_returns_none(self):
        assert optional_string("") is None

    def test_whitespace_string_returns_none(self):
        assert optional_string("  ") is None

    def test_non_empty_string_returns_trimmed(self):
        assert optional_string("  hello  ") == "hello"

    def test_non_string_value_is_converted(self):
        assert optional_string(42) == "42"


class TestExtractScopes:
    def test_scp_claim_string(self):
        claims = {"scp": "read write"}
        assert extract_scopes(claims) == {"read", "write"}

    def test_scope_claim_string(self):
        claims = {"scope": "openid profile"}
        assert extract_scopes(claims) == {"openid", "profile"}

    def test_roles_claim_list(self):
        claims = {"roles": ["admin", "user"]}
        assert extract_scopes(claims) == {"admin", "user"}

    def test_roles_claim_with_none(self):
        claims = {"roles": ["admin", None]}
        assert extract_scopes(claims) == {"admin"}

    def test_all_claim_types_merged(self):
        claims = {
            "scp": "read",
            "scope": "openid",
            "roles": ["admin"],
        }
        assert extract_scopes(claims) == {"read", "openid", "admin"}

    def test_no_scope_claims_returns_empty(self):
        assert extract_scopes({}) == set()

    def test_unsupported_types_ignored(self):
        claims = {"scp": 123, "scope": None, "roles": "not-a-list"}
        assert extract_scopes(claims) == set()


class TestExtractAudiences:
    def test_list_audience(self):
        claims = {"aud": ["api://default", "other"]}
        assert extract_audiences(claims) == ("api://default", "other")

    def test_string_audience(self):
        claims = {"aud": "api://default"}
        assert extract_audiences(claims) == ("api://default",)

    def test_missing_audience(self):
        claims = {}
        result = extract_audiences(claims)
        assert result == ("None",)

    def test_single_element_list(self):
        claims = {"aud": ["single"]}
        assert extract_audiences(claims) == ("single",)


class TestPrincipalSubject:
    def test_oid_used_when_present(self):
        claims = {"oid": "user-oid", "sub": "user-sub"}
        assert principal_subject(claims) == "user-oid"

    def test_sub_fallback_when_oid_missing(self):
        claims = {"sub": "user-sub"}
        assert principal_subject(claims) == "user-sub"

    def test_empty_oid_falls_back_to_sub(self):
        claims = {"oid": "", "sub": "user-sub"}
        assert principal_subject(claims) == "user-sub"

    def test_none_oid_falls_back_to_sub(self):
        claims = {"oid": None, "sub": "user-sub"}
        assert principal_subject(claims) == "user-sub"


class TestNormalizeResourceUri:
    def test_lowercases_scheme_and_host(self):
        result = normalize_resource_uri("HTTP://EXAMPLE.COM/Path")
        assert result == "http://example.com/Path"

    def test_strips_default_port(self):
        result = normalize_resource_uri("https://example.com:443/path")
        assert result == "https://example.com/path"

    def test_keeps_non_default_port(self):
        result = normalize_resource_uri("https://example.com:8443/path")
        assert result == "https://example.com:8443/path"

    def test_strips_trailing_slash_from_path(self):
        result = normalize_resource_uri("https://example.com/path/")
        assert result == "https://example.com/path"

    def test_normalizes_empty_path(self):
        result = normalize_resource_uri("https://example.com/")
        assert result == "https://example.com"

    def test_no_scheme_returns_none_for_empty(self):
        result = normalize_resource_uri("")
        assert result is None

    def test_no_scheme_returns_value(self):
        result = normalize_resource_uri("api://default")
        assert result == "api://default"


class TestAudiencesMatchResource:
    def test_audience_matches_configured_resource(self):
        assert audiences_match_resource(
            ("http://example.com/api",),
            ("http://example.com/api",),
        )

    def test_audience_does_not_match(self):
        assert not audiences_match_resource(
            ("http://other.com/api",),
            ("http://example.com/api",),
        )

    def test_empty_configured_resources_returns_false(self):
        assert not audiences_match_resource(
            ("http://example.com/api",),
            (),
        )

    def test_multiple_audiences_one_matches(self):
        assert audiences_match_resource(
            ("http://other.com/api", "http://example.com/api"),
            ("http://example.com/api",),
        )

    def test_normalization_applied_to_both_sides(self):
        assert audiences_match_resource(
            ("HTTP://EXAMPLE.COM:80/api",),
            ("http://example.com/api",),
        )


class TestBuildAuthChallenge:
    def test_basic_challenge(self):
        challenge = build_auth_challenge(
            resource_metadata_url="http://example.com/resource",
            scopes=["read", "write"],
        )
        assert 'Bearer realm="agent-proxy"' in challenge
        assert 'resource_metadata="http://example.com/resource"' in challenge
        assert 'scope="read write"' in challenge or 'scope="write read"' in challenge

    def test_challenge_with_error(self):
        challenge = build_auth_challenge(
            resource_metadata_url="http://example.com/resource",
            scopes=[],
            error="insufficient_scope",
        )
        assert 'error="insufficient_scope"' in challenge

    def test_challenge_with_error_description(self):
        challenge = build_auth_challenge(
            resource_metadata_url="http://example.com/resource",
            scopes=[],
            error_description="Token missing required scope.",
        )
        assert 'error_description="Token missing required scope."' in challenge

    def test_no_scopes_omits_scope(self):
        challenge = build_auth_challenge(
            resource_metadata_url="http://example.com/resource",
            scopes=[],
        )
        assert "scope=" not in challenge


class TestFindJwk:
    def test_finds_key_by_kid(self):
        jwks = {
            "keys": [{"kid": "key-1", "k": "value1"}, {"kid": "key-2", "k": "value2"}]
        }
        result = find_jwk(jwks, "key-2")
        assert result == {"kid": "key-2", "k": "value2"}

    def test_returns_none_when_kid_not_found(self):
        jwks = {"keys": [{"kid": "key-1", "k": "value1"}]}
        result = find_jwk(jwks, "key-unknown")
        assert result is None

    def test_returns_none_when_keys_empty(self):
        jwks = {"keys": []}
        result = find_jwk(jwks, "key-1")
        assert result is None
