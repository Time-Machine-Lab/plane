#!/bin/sh

set -u
PLANE_SCRIPT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export PLANE_SCRIPT_ROOT
. "$PLANE_SCRIPT_ROOT/lib/plane.sh"

plane_setup_main "$@"
exit $?
