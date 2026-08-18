/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import useSWR from "swr";
import { Loader } from "@plane/ui";
// components
import { PageWrapper } from "@/components/common/page-wrapper";
// hooks
import { useInstance } from "@/hooks/store";
// types
import type { Route } from "./+types/page";
// local
import { DiscordConfigForm } from "./discord-config-form";

const DiscordConfigurationPage = observer(function DiscordConfigurationPage(_props: Route.ComponentProps) {
  const { discordConfiguration, fetchDiscordConfiguration } = useInstance();
  const { error, isLoading } = useSWR("DISCORD_CONFIGURATION", () => fetchDiscordConfiguration());

  return (
    <PageWrapper
      header={{
        title: "Discord notifications",
        description: "Send selected Plane work item events to one Discord channel using an Incoming Webhook.",
      }}
    >
      {error ? (
        <div
          role="alert"
          className="border-danger-primary border-l-2 bg-danger-subtle px-3 py-2 text-13 text-danger-primary"
        >
          You do not have access to this configuration, or it could not be loaded.
        </div>
      ) : isLoading || !discordConfiguration ? (
        <Loader className="space-y-8">
          <Loader.Item height="40px" width="35%" />
          <div className="grid max-w-4xl grid-cols-1 gap-5 md:grid-cols-2">
            <Loader.Item height="64px" />
            <Loader.Item height="64px" />
          </div>
          <Loader.Item height="120px" width="80%" />
        </Loader>
      ) : (
        <DiscordConfigForm config={discordConfiguration} />
      )}
    </PageWrapper>
  );
});

export const meta: Route.MetaFunction = () => [{ title: "Discord Settings - God Mode" }];

export default DiscordConfigurationPage;
