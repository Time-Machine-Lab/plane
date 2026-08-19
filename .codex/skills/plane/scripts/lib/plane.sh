#!/bin/sh

PLANE_MCP_NAME=plane
PLANE_MCP_PROTOCOL_VERSION=2025-03-26

plane_python() {
    if command -v python3 >/dev/null 2>&1; then
        python3 "$@"
    else
        printf '%s\n' "Python 3 is required by the Plane POSIX scripts." >&2
        return 127
    fi
}

plane_helper() {
    plane_python "$PLANE_SCRIPT_ROOT/lib/plane_helper.py" "$@"
}

plane_redact() {
    plane_helper redact
}

plane_codex_home() {
    if [ -n "${CODEX_HOME:-}" ]; then
        printf '%s\n' "$CODEX_HOME"
    else
        printf '%s\n' "$HOME/.codex"
    fi
}

plane_profile_path() {
    if [ -n "${PLANE_PROFILE_PATH:-}" ]; then
        printf '%s\n' "$PLANE_PROFILE_PATH"
    else
        printf '%s/plane/profile.json\n' "$(plane_codex_home)"
    fi
}

plane_codex_config_path() {
    printf '%s/config.toml\n' "$(plane_codex_home)"
}

plane_codex() {
    codex "$@"
}

plane_assert_preflight() {
    command -v codex >/dev/null 2>&1 || {
        printf '%s\n' "Codex CLI is not installed or is not available on PATH." >&2
        return 1
    }
    command -v curl >/dev/null 2>&1 || {
        printf '%s\n' "curl is required by the Plane POSIX scripts." >&2
        return 1
    }
    plane_python --version >/dev/null 2>&1 || return 1
    help_output=$(plane_codex mcp add --help 2>&1) || return 1
    case "$help_output" in
        *--url*) ;;
        *)
            printf '%s\n' "This Codex CLI does not support remote HTTP MCP servers." >&2
            return 1
            ;;
    esac
}

plane_write_static_token() {
    config_path=$(plane_codex_config_path)
    plane_helper config-write-token --path "$config_path" || return 1
    chmod 600 "$config_path" 2>/dev/null || true
}

plane_get_token() {
    if [ -n "${PLANE_API_TOKEN:-}" ]; then
        plane_helper validate-token || return 1
        PLANE_TOKEN_SOURCE=environment
        export PLANE_TOKEN_SOURCE
        return 0
    fi
    if [ "${PLANE_NON_INTERACTIVE:-0}" = 1 ]; then
        printf '%s\n' "PLANE_API_TOKEN is not available in this process." >&2
        return 1
    fi
    if [ ! -t 0 ]; then
        printf '%s\n' "Masked token input requires an interactive terminal." >&2
        return 1
    fi
    printf '%s' "Plane API token: " >&2
    old_settings=$(stty -g) || return 1
    trap 'stty "$old_settings"; exit 130' HUP INT TERM
    stty -echo
    IFS= read -r PLANE_API_TOKEN
    stty "$old_settings"
    trap - HUP INT TERM
    printf '\n' >&2
    if [ -z "$PLANE_API_TOKEN" ]; then
        printf '%s\n' "Plane API token is empty." >&2
        return 1
    fi
    export PLANE_API_TOKEN
    plane_helper validate-token || {
        PLANE_API_TOKEN=
        export PLANE_API_TOKEN
        return 1
    }
    PLANE_TOKEN_SOURCE=masked_prompt
    export PLANE_API_TOKEN PLANE_TOKEN_SOURCE
}

plane_http_request() {
    request_method=$1
    auth_type=$2
    url=$3
    output_path=$4
    request_body_path=${5:-}
    plane_helper validate-token || return 2
    case "$auth_type" in
        api_key) header="X-Api-Key: $PLANE_API_TOKEN" ;;
        bearer) header="Authorization: Bearer $PLANE_API_TOKEN" ;;
        *) return 2 ;;
    esac
    if [ "$request_method" = post ]; then
        request_data='{}'
        if [ -n "$request_body_path" ]; then
            request_data="@$request_body_path"
        fi
        printf 'header = "%s"\n' "$header" |
            curl --config - --silent --show-error --connect-timeout 5 --max-time 15 \
                --request POST --header 'Content-Type: application/json' \
                --header 'Accept: application/json, text/event-stream' \
                --header "MCP-Protocol-Version: $PLANE_MCP_PROTOCOL_VERSION" --data-binary "$request_data" \
                --output "$output_path" --write-out '%{http_code}' --url "$url"
    else
        printf 'header = "%s"\n' "$header" |
            curl --config - --silent --show-error --connect-timeout 5 --max-time 15 \
                --output "$output_path" --write-out '%{http_code}' --url "$url"
    fi
}

plane_validate_connection() {
    origin=$1
    slug=$2
    mcp_url=$3
    temporary_dir=$(mktemp -d "${TMPDIR:-/tmp}/plane-setup.XXXXXX") || return 1
    trap 'rm -rf "$temporary_dir"' EXIT HUP INT TERM

    status=$(plane_http_request get api_key "$origin/api/v1/users/me/" "$temporary_dir/user.json") || {
        printf '%s\n' "Network, DNS, or TLS connection failed." >&2
        return 1
    }
    case "$status" in
        200) ;;
        401|403) printf '%s\n' "Plane rejected the API token." >&2; return 1 ;;
        *) printf '%s\n' "Plane identity validation failed with HTTP $status." >&2; return 1 ;;
    esac

    status=$(plane_http_request get api_key "$origin/api/v1/workspaces/$slug/projects/?per_page=1" "$temporary_dir/workspace.json") || {
        printf '%s\n' "Network, DNS, or TLS connection failed." >&2
        return 1
    }
    case "$status" in
        200) ;;
        401|403|404) printf '%s\n' "The authenticated user cannot access the requested workspace." >&2; return 1 ;;
        *) printf '%s\n' "Workspace validation failed with HTTP $status." >&2; return 1 ;;
    esac

    status=$(plane_http_request post bearer "$mcp_url" "$temporary_dir/mcp.txt") || {
        printf '%s\n' "Network, DNS, or TLS connection failed." >&2
        return 1
    }
    case "$status" in
        200|400|422) ;;
        401|403) printf '%s\n' "The MCP endpoint rejected the API token." >&2; return 1 ;;
        404|5??) printf '%s\n' "The Plane MCP endpoint is not available." >&2; return 1 ;;
        *) printf '%s\n' "The Plane MCP endpoint returned unexpected HTTP $status." >&2; return 1 ;;
    esac

    raw_user=$(plane_helper user-label --path "$temporary_dir/user.json") || return 1
    printf '%s' "$raw_user" | plane_redact
    result=$?
    rm -rf "$temporary_dir"
    trap - EXIT HUP INT TERM
    return $result
}

plane_setup_main() {
    workspace_url=
    workspace_slug=
    PLANE_NON_INTERACTIVE=0
    replace=0
    json=0
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --workspace-url) workspace_url=${2:-}; shift 2 ;;
            --workspace-slug) workspace_slug=${2:-}; shift 2 ;;
            --non-interactive) PLANE_NON_INTERACTIVE=1; shift ;;
            --replace) replace=1; shift ;;
            --json) json=1; shift ;;
            *) printf '%s\n' "Unknown option: $1" >&2; return 2 ;;
        esac
    done
    export PLANE_NON_INTERACTIVE
    if [ -z "$workspace_url" ]; then
        printf '%s\n' "--workspace-url is required." >&2
        return 2
    fi

    plane_assert_preflight || return 1
    if [ -n "$workspace_slug" ]; then
        normalized=$(plane_helper normalize-url --url "$workspace_url" --slug "$workspace_slug") || return 1
    else
        normalized=$(plane_helper normalize-url --url "$workspace_url") || return 1
    fi
    origin=$(printf '%s\n' "$normalized" | sed -n '1p')
    slug=$(printf '%s\n' "$normalized" | sed -n '2p')
    mcp_url=$(printf '%s\n' "$normalized" | sed -n '3p')
    plane_get_token || return 1
    user=$(plane_validate_connection "$origin" "$slug" "$mcp_url") || return 1

    existing=
    if existing=$(plane_codex mcp get "$PLANE_MCP_NAME" --json 2>/dev/null); then
        if printf '%s' "$existing" | plane_helper config-match --url "$mcp_url"; then
            mcp_state=reused
        else
            if [ "$replace" -ne 1 ]; then
                if [ "$PLANE_NON_INTERACTIVE" -eq 1 ]; then
                    printf '%s\n' "A different plane MCP entry exists. Re-run with --replace." >&2
                    return 1
                fi
                printf '%s' "A different plane MCP entry exists. Replace it? [y/N] " >&2
                IFS= read -r answer
                case "$answer" in y|Y|yes|YES) ;; *) printf '%s\n' "The existing plane MCP entry was not changed." >&2; return 1 ;; esac
            fi
            plane_codex mcp remove "$PLANE_MCP_NAME" >/dev/null || return 1
            plane_codex mcp add "$PLANE_MCP_NAME" --url "$mcp_url" >/dev/null || return 1
            plane_write_static_token || return 1
            mcp_state=replaced
        fi
    else
        plane_codex mcp add "$PLANE_MCP_NAME" --url "$mcp_url" >/dev/null || return 1
        plane_write_static_token || return 1
        mcp_state=added
    fi

    profile_path=$(plane_profile_path)
    plane_helper profile-write --path "$profile_path" --origin "$origin" --slug "$slug" || return 1
    if [ "$json" -eq 1 ]; then
        plane_helper setup-output --origin "$origin" --slug "$slug" --user "$user" --mcp-state "$mcp_state" --token-source "$PLANE_TOKEN_SOURCE" --profile-path "$profile_path"
    else
        plane_helper setup-output --origin "$origin" --slug "$slug" --user "$user" --mcp-state "$mcp_state" --token-source "$PLANE_TOKEN_SOURCE" --profile-path "$profile_path" --human
    fi
}

plane_add_check() {
    check_name=$1
    check_status=$2
    check_category=$3
    check_detail=$(printf '%s' "$4" | plane_redact | tr '\t\r\n' '   ')
    printf '%s\t%s\t%s\t%s\n' "$check_name" "$check_status" "$check_category" "$check_detail" >>"$PLANE_CHECKS_FILE"
}

plane_status_probe() {
    slug=$1
    mcp_url=$2
    request_path=$3
    output_path=$4
    plane_helper probe-request --slug "$slug" >"$request_path" || return 1
    status=$(plane_http_request post bearer "$mcp_url" "$output_path" "$request_path" 2>/dev/null) || {
        printf '%s\n' "The deterministic plane_status MCP probe could not reach the endpoint."
        return 1
    }
    case "$status" in
        200) plane_helper probe-valid --path "$output_path" --slug "$slug" 2>/dev/null ;;
        401|403) printf '%s\n' "The Plane MCP endpoint rejected the credential."; return 1 ;;
        *) printf '%s\n' "The plane_status MCP request returned HTTP $status."; return 1 ;;
    esac
}

plane_doctor_main() {
    json=0
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --json) json=1; shift ;;
            *) printf '%s\n' "Unknown option: $1" >&2; return 2 ;;
        esac
    done

    temporary_dir=$(mktemp -d "${TMPDIR:-/tmp}/plane-doctor.XXXXXX") || return 1
    trap 'rm -rf "$temporary_dir"' EXIT HUP INT TERM
    PLANE_CHECKS_FILE="$temporary_dir/checks.tsv"
    export PLANE_CHECKS_FILE
    : >"$PLANE_CHECKS_FILE"
    origin=
    slug=
    mcp_url=
    user=
    PLANE_API_TOKEN=
    export PLANE_API_TOKEN

    if plane_assert_preflight >/dev/null 2>&1; then
        plane_add_check codex pass local_configuration "Codex remote MCP support is available."
    else
        plane_add_check codex fail local_configuration "Codex remote MCP support is unavailable."
    fi

    profile_path=$(plane_profile_path)
    if normalized=$(plane_helper profile-read --path "$profile_path" 2>/dev/null); then
        origin=$(printf '%s\n' "$normalized" | sed -n '1p')
        slug=$(printf '%s\n' "$normalized" | sed -n '2p')
        mcp_url=$(printf '%s\n' "$normalized" | sed -n '3p')
        plane_add_check profile pass local_configuration "The non-secret Plane profile is valid."
    else
        plane_add_check profile fail local_configuration "Plane profile is missing or invalid. Run setup first."
    fi

    if [ -n "$mcp_url" ]; then
        if existing=$(plane_codex mcp get "$PLANE_MCP_NAME" --json 2>/dev/null) &&
            PLANE_API_TOKEN=$(printf '%s' "$existing" | plane_helper config-token 2>/dev/null) &&
            export PLANE_API_TOKEN &&
            printf '%s' "$existing" | plane_helper config-match --url "$mcp_url" >/dev/null 2>&1
        then
            plane_add_check mcp_configuration pass local_configuration "The plane MCP entry matches the profile."
        else
            PLANE_API_TOKEN=
            export PLANE_API_TOKEN
            plane_add_check mcp_configuration fail local_configuration "The plane MCP entry is missing or does not match the profile."
        fi
    else
        plane_add_check mcp_configuration skipped local_configuration "Skipped because the profile is unavailable."
    fi

    if [ -z "${PLANE_API_TOKEN:-}" ]; then
        plane_add_check authentication fail authentication "The plane MCP entry does not contain a Bearer credential."
        plane_add_check reachability skipped reachability_tls "Skipped because connection inputs are unavailable."
        plane_add_check workspace skipped workspace_authorization "Skipped because connection inputs are unavailable."
    elif [ -n "$mcp_url" ]; then
        if status=$(plane_http_request post bearer "$mcp_url" "$temporary_dir/mcp.txt" 2>/dev/null); then
            case "$status" in
                200|400|422) plane_add_check reachability pass reachability_tls "The Plane MCP endpoint is reachable over TLS." ;;
                401|403) plane_add_check reachability fail reachability_tls "The Plane MCP endpoint rejected the credential." ;;
                *) plane_add_check reachability fail reachability_tls "The Plane MCP endpoint is unavailable or returned HTTP $status." ;;
            esac
        else
            plane_add_check reachability fail reachability_tls "Network, DNS, or TLS connection failed."
        fi

        if status=$(plane_http_request get api_key "$origin/api/v1/users/me/" "$temporary_dir/user.json" 2>/dev/null); then
            case "$status" in
                200)
                    if raw_user=$(plane_helper user-label --path "$temporary_dir/user.json" 2>/dev/null); then
                        user=$(printf '%s' "$raw_user" | plane_redact)
                        plane_add_check authentication pass authentication "Plane accepted the configured API token."
                    else
                        plane_add_check authentication fail authentication "Plane returned invalid identity JSON."
                    fi
                    ;;
                401|403) plane_add_check authentication fail authentication "Plane rejected the API token." ;;
                *) plane_add_check authentication fail authentication "Identity check returned HTTP $status." ;;
            esac
        else
            plane_add_check authentication fail authentication "Network, DNS, or TLS connection failed."
        fi

        if [ -n "$user" ]; then
            if status=$(plane_http_request get api_key "$origin/api/v1/workspaces/$slug/projects/?per_page=1" "$temporary_dir/workspace.json" 2>/dev/null); then
                case "$status" in
                    200) plane_add_check workspace pass workspace_authorization "The authenticated user can access the configured workspace." ;;
                    401|403|404) plane_add_check workspace fail workspace_authorization "The user cannot access the configured workspace." ;;
                    *) plane_add_check workspace fail workspace_authorization "Workspace check returned HTTP $status." ;;
                esac
            else
                plane_add_check workspace fail workspace_authorization "Network, DNS, or TLS connection failed."
            fi
        else
            plane_add_check workspace skipped workspace_authorization "Skipped because authentication failed."
        fi
    else
        plane_add_check reachability skipped reachability_tls "Skipped because connection inputs are unavailable."
        plane_add_check workspace skipped workspace_authorization "Skipped because connection inputs are unavailable."
    fi

    if ! grep -q "$(printf '\tfail\t')" "$PLANE_CHECKS_FILE" && [ -n "$slug" ]; then
        if probe_detail=$(plane_status_probe "$slug" "$mcp_url" "$temporary_dir/probe-request.json" "$temporary_dir/probe-response.json"); then
            plane_add_check tools pass tool_availability "$probe_detail"
        else
            plane_add_check tools fail tool_availability "${probe_detail:-The deterministic plane_status MCP probe failed.}"
        fi
    else
        plane_add_check tools skipped tool_availability "Skipped until earlier failures are resolved."
    fi

    if [ "$json" -eq 1 ]; then
        plane_helper doctor-output --checks "$PLANE_CHECKS_FILE" --origin "$origin" --slug "$slug" --user "$user"
    else
        plane_helper doctor-output --checks "$PLANE_CHECKS_FILE" --origin "$origin" --slug "$slug" --user "$user" --human
    fi
    result=$?
    rm -rf "$temporary_dir"
    trap - EXIT HUP INT TERM
    return $result
}
