/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { PenTool } from "lucide-react";
// extensions
import { getCanvasTranslation, type TSlashCommandAdditionalOption } from "@/extensions";
// types
import type { IEditorProps } from "@/types";

type Props = Pick<IEditorProps, "disabledExtensions" | "flaggedExtensions" | "translate">;

export const coreEditorAdditionalSlashCommandOptions = (props: Props): TSlashCommandAdditionalOption[] => {
  const { disabledExtensions, translate } = props;
  const options: TSlashCommandAdditionalOption[] = [];
  if (!disabledExtensions.includes("canvas")) {
    options.push({
      commandKey: "canvas",
      key: "canvas",
      title: getCanvasTranslation(translate, "canvas.slash.title"),
      description: getCanvasTranslation(translate, "canvas.slash.description"),
      searchTerms: ["canvas", "drawing", "diagram", "whiteboard"],
      icon: <PenTool className="size-3.5" />,
      command: ({ editor, range }) => {
        editor
          .chain()
          .focus()
          .deleteRange(range)
          .insertCanvas({ title: getCanvasTranslation(translate, "canvas.untitled") })
          .run();
      },
      section: "general",
      pushAfter: "image",
    });
  }
  return options;
};
