/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef } from "react";
import { observer } from "mobx-react";
import { Logo } from "@plane/propel/emoji-icon-picker";
import { PageIcon } from "@plane/propel/icons";
import { useTranslation } from "@plane/i18n";
// plane imports
import { getPageName } from "@plane/utils";
// components
import { ListItem } from "@/components/core/list";
import { BlockItemAction } from "@/components/pages/list/block-item-action";
// hooks
import { usePlatformOS } from "@/hooks/use-platform-os";
// plane web hooks
import type { EPageStoreType } from "@/hooks/store";
import { usePage } from "@/hooks/store";

type TPageListBlock = {
  pageId: string;
  storeType: EPageStoreType;
};

export const PageListBlock = observer(function PageListBlock(props: TPageListBlock) {
  const { pageId, storeType } = props;
  // refs
  const parentRef = useRef(null);
  // hooks
  const page = usePage({
    pageId,
    storeType,
  });
  const { isMobile } = usePlatformOS();
  const { t } = useTranslation();
  // handle page check
  if (!page) return null;
  // derived values
  const { name, logo_props, getRedirectionLink, path, depth, access, is_locked, archived_at } = page;

  return (
    <ListItem
      prependTitleElement={
        <>
          {logo_props?.in_use ? (
            <Logo logo={logo_props} size={16} type="lucide" />
          ) : (
            <PageIcon className="h-4 w-4 text-tertiary" />
          )}
        </>
      }
      title={getPageName(name)}
      appendTitleElement={
        <span className="hidden min-w-0 items-center gap-3 text-11 text-tertiary md:flex">
          {path && path.length > 1 && (
            <span className="max-w-80 truncate">{path.map((item) => getPageName(item.name)).join(" / ")}</span>
          )}
          {depth && <span className="tabular-nums">L{depth}</span>}
          {access === 1 && <span>{t("common.access.private")}</span>}
          {is_locked && <span>{t("wiki_collections.list.restricted_access")}</span>}
          {archived_at && <span>{t("wiki_collections.predefined.archived")}</span>}
        </span>
      }
      itemLink={getRedirectionLink()}
      actionableItems={<BlockItemAction page={page} parentRef={parentRef} storeType={storeType} />}
      isMobile={isMobile}
      parentRef={parentRef}
    />
  );
});
