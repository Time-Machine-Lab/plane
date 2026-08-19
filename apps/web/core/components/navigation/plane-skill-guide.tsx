/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { ExternalLink, Sparkles, X } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { IconButton } from "@plane/propel/icon-button";
import { CopyIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Tooltip } from "@plane/propel/tooltip";
import { EModalPosition, EModalWidth, ModalCore } from "@plane/ui";
import { copyTextToClipboard } from "@plane/utils";

const PLANE_REPOSITORY_URL = "https://github.com/Time-Machine-Lab/plane";

type TPromptBlockProps = {
  label: string;
  onCopy: () => void;
  prompt: string;
};

function PromptBlock(props: TPromptBlockProps) {
  const { label, onCopy, prompt } = props;

  return (
    <div className="flex min-w-0 items-start gap-2 rounded-md bg-layer-1 p-3">
      <code className="font-mono min-w-0 flex-1 text-12 leading-5 break-words whitespace-pre-wrap text-primary">
        {prompt}
      </code>
      <button
        type="button"
        onClick={onCopy}
        aria-label={label}
        className="flex size-7 shrink-0 items-center justify-center rounded-md text-icon-secondary outline-none hover:bg-layer-1-hover hover:text-icon-primary focus-visible:ring-2 focus-visible:ring-accent-strong"
      >
        <CopyIcon className="size-4" />
      </button>
    </div>
  );
}

export function PlaneSkillGuide() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  const handleCopy = (prompt: string) => {
    copyTextToClipboard(prompt).then(() =>
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("success"),
        message: t("copied_to_clipboard"),
      })
    );
  };

  const installPrompt = t("plane_skill_guide.install_prompt");
  const connectPrompt = t("plane_skill_guide.connect_prompt");

  return (
    <>
      <Tooltip tooltipContent={t("plane_skill_guide.tooltip")} position="bottom">
        <Button
          variant="secondary"
          size="xl"
          prependIcon={<Sparkles aria-hidden="true" />}
          onClick={() => setIsOpen(true)}
          aria-label={t("plane_skill_guide.tooltip")}
          className="focus-visible:ring-2 focus-visible:ring-accent-strong"
        >
          {t("plane_skill_guide.button_label")}
        </Button>
      </Tooltip>

      <ModalCore
        isOpen={isOpen}
        handleClose={() => setIsOpen(false)}
        position={EModalPosition.CENTER}
        width={EModalWidth.XXXL}
      >
        <div className="flex max-h-[calc(100dvh-2rem)] flex-col overflow-hidden sm:max-h-[90vh]">
          <div className="flex shrink-0 items-start justify-between gap-4 border-b border-subtle px-4 py-4 sm:px-6">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-layer-1 text-icon-primary">
                  <Sparkles className="size-4" aria-hidden="true" />
                </div>
                <h2 className="text-18 font-semibold text-primary">{t("plane_skill_guide.title")}</h2>
              </div>
              <p className="mt-2 text-13 leading-5 text-secondary">{t("plane_skill_guide.description")}</p>
            </div>
            <IconButton
              variant="ghost"
              size="lg"
              icon={X}
              onClick={() => setIsOpen(false)}
              aria-label={t("close")}
              className="shrink-0 focus-visible:ring-2 focus-visible:ring-accent-strong"
            />
          </div>

          <div className="flex-1 space-y-5 overflow-y-auto px-4 py-5 sm:px-6">
            <a
              href={PLANE_REPOSITORY_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="flex min-w-0 items-center gap-2 rounded-md border border-subtle bg-layer-1 px-3 py-2 text-13 outline-none hover:bg-layer-1-hover focus-visible:ring-2 focus-visible:ring-accent-strong"
            >
              <span className="shrink-0 font-medium text-secondary">{t("plane_skill_guide.repository_label")}</span>
              <span className="min-w-0 flex-1 truncate text-link-primary">{PLANE_REPOSITORY_URL}</span>
              <ExternalLink className="size-3.5 shrink-0 text-icon-secondary" aria-hidden="true" />
            </a>

            <section className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3">
              <div className="flex size-8 items-center justify-center rounded-full bg-layer-1 text-13 font-semibold text-secondary">
                1
              </div>
              <div className="min-w-0 space-y-3">
                <h3 className="pt-1 text-14 font-semibold text-primary">{t("plane_skill_guide.install_title")}</h3>
                <PromptBlock
                  label={t("plane_skill_guide.copy_prompt")}
                  prompt={installPrompt}
                  onCopy={() => handleCopy(installPrompt)}
                />
              </div>
            </section>

            <section className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3 border-t border-subtle pt-5">
              <div className="flex size-8 items-center justify-center rounded-full bg-layer-1 text-13 font-semibold text-secondary">
                2
              </div>
              <div className="min-w-0 space-y-3">
                <h3 className="pt-1 text-14 font-semibold text-primary">{t("plane_skill_guide.connect_title")}</h3>
                <PromptBlock
                  label={t("plane_skill_guide.copy_prompt")}
                  prompt={connectPrompt}
                  onCopy={() => handleCopy(connectPrompt)}
                />

                <p className="text-13 leading-5 text-secondary">{t("plane_skill_guide.provide_details")}</p>

                <div className="space-y-2 rounded-md border border-subtle bg-layer-1 p-3">
                  <h4 className="text-13 font-semibold text-primary">{t("plane_skill_guide.workspace_url_title")}</h4>
                  <p className="text-12 leading-5 text-secondary">{t("plane_skill_guide.workspace_url_format")}</p>
                  <code className="font-mono block rounded-md bg-layer-2 px-2.5 py-2 text-12 break-all text-primary">
                    {t("plane_skill_guide.workspace_url_example")}
                  </code>
                  <p className="text-12 leading-5 text-tertiary">{t("plane_skill_guide.workspace_url_warning")}</p>
                </div>

                <div className="space-y-2 rounded-md border border-subtle bg-layer-1 p-3">
                  <h4 className="text-13 font-semibold text-primary">{t("plane_skill_guide.api_token_title")}</h4>
                  <p className="text-12 font-medium text-secondary">{t("plane_skill_guide.api_token_path_label")}</p>
                  <p className="rounded-md bg-layer-2 px-2.5 py-2 text-12 leading-5 text-primary">
                    {t("plane_skill_guide.api_token_path")}
                  </p>
                  <p className="text-12 leading-5 text-tertiary">{t("plane_skill_guide.api_token_warning")}</p>
                </div>
              </div>
            </section>

            <div className="rounded-md border border-success-subtle bg-success-subtle px-3 py-2.5">
              <p className="text-13 font-semibold text-success-primary">{t("plane_skill_guide.connected_title")}</p>
              <p className="mt-1 text-12 leading-5 text-secondary">{t("plane_skill_guide.connected_description")}</p>
            </div>

            <p className="text-12 leading-5 text-tertiary">{t("plane_skill_guide.security_note")}</p>
          </div>

          <div className="flex shrink-0 justify-end border-t border-subtle px-4 py-3 sm:px-6">
            <Button variant="secondary" size="lg" onClick={() => setIsOpen(false)}>
              {t("close")}
            </Button>
          </div>
        </div>
      </ModalCore>
    </>
  );
}
