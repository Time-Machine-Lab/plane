/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Dialog } from "@headlessui/react";
import type { NodeViewProps } from "@tiptap/react";
import type { HocuspocusProvider } from "@hocuspocus/provider";
import { NodeViewWrapper } from "@tiptap/react";
import { AlertCircle, Copy, Expand, LoaderCircle, Maximize2, Minimize2, Trash2, X } from "lucide-react";
import { cn } from "@plane/utils";
import { CORE_EXTENSIONS } from "@/constants/extension";
import {
  CANVAS_SAVE_DEBOUNCE_MS,
  ECanvasAttributeNames,
  MAX_CANVAS_TITLE_LENGTH,
  type TCanvasAttributes,
  type TCanvasAwarenessState,
  type TCanvasPreviewSize,
  type TCanvasSaveStatus,
  type TCanvasScene,
  type TCanvasValidationErrorCode,
} from "./types";
import { getCanvasTranslation } from "./translations";
import {
  decodeCanvasScene,
  encodeCanvasScene,
  getCanvasPreviewDataUri,
  getCanvasPreviewSize,
  getCanvasSceneFingerprint,
  isCurrentCanvasSaveRevision,
  normalizeCanvasTitle,
  shouldRenderCanvasPreview,
  validateCanvasPreview,
} from "./utils";
import type { TEditorTranslation } from "@/types/editor";

const LazyExcalidrawAdapter = lazy(() =>
  import("./excalidraw-adapter").then((module) => ({ default: module.ExcalidrawAdapter }))
);

type Props = NodeViewProps & {
  isEditable: boolean;
  provider?: HocuspocusProvider;
  userName?: string;
  translate?: TEditorTranslation;
};

const STATUS_KEYS: Record<Exclude<TCanvasSaveStatus, "idle">, string> = {
  saving: "canvas.status.saving",
  saved: "canvas.status.saved",
  failed: "canvas.status.failed",
  oversized: "canvas.error.oversized",
  "unsupported-file": "canvas.error.unsupported_file",
};

const getErrorStatus = (code: TCanvasValidationErrorCode): TCanvasSaveStatus => {
  if (code === "oversized") return "oversized";
  if (code === "unsupported-file") return "unsupported-file";
  return "failed";
};

const readRemoteEditor = (provider: HocuspocusProvider | undefined, canvasId: string): string | null => {
  const awareness = provider?.awareness;
  if (!awareness) return null;
  let owner: { clientId: number; userName: string } | null = null;
  for (const [clientId, state] of awareness.getStates()) {
    const active = state.planeCanvas as TCanvasAwarenessState | undefined;
    if (active?.canvasId === canvasId && (owner === null || clientId < owner.clientId)) {
      owner = { clientId, userName: active.userName ?? "" };
    }
  }
  return owner !== null && owner.clientId !== awareness.clientID ? owner.userName : null;
};

export function CanvasNodeView(props: Props) {
  const { editor, isEditable, node, provider, translate, userName } = props;
  const t = useCallback(
    (key: string, params?: Record<string, unknown>) => getCanvasTranslation(translate, key, params),
    [translate]
  );
  const attrs = node.attrs as TCanvasAttributes;
  const canvasId = attrs[ECanvasAttributeNames.ID];
  const decodedScene = useMemo(
    () => decodeCanvasScene(attrs[ECanvasAttributeNames.SCENE], Number(attrs[ECanvasAttributeNames.SCENE_VERSION])),
    [attrs]
  );
  const preview = useMemo(() => getCanvasPreviewDataUri(attrs), [attrs]);
  const [isOpen, setIsOpen] = useState(false);
  const [status, setStatus] = useState<TCanvasSaveStatus>("idle");
  const [title, setTitle] = useState(attrs[ECanvasAttributeNames.TITLE]);
  const [remoteEditor, setRemoteEditor] = useState<string | null>(() => readRemoteEditor(provider, canvasId));
  const [theme, setTheme] = useState<"dark" | "light">("light");
  const [externalSceneRevision, setExternalSceneRevision] = useState(0);
  const pendingSceneRef = useRef<TCanvasScene | null>(null);
  const pendingSceneRevisionRef = useRef(0);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const titleInputRef = useRef<HTMLInputElement | null>(null);
  const lastSavedSceneRef = useRef(decodedScene.ok ? decodedScene.value : null);
  const lastSavedSceneEncodedRef = useRef(attrs[ECanvasAttributeNames.SCENE]);
  const lastSavedSceneFingerprintRef = useRef(decodedScene.ok ? getCanvasSceneFingerprint(decodedScene.value) : null);
  const pendingSceneFingerprintRef = useRef<string | null>(null);

  const isUnsupportedVersion = !decodedScene.ok && decodedScene.code === "unsupported-version";
  const isReadOnly = !isEditable || remoteEditor !== null || isUnsupportedVersion;
  const displaySize = getCanvasPreviewSize(Number(attrs[ECanvasAttributeNames.PREVIEW_WIDTH]));

  useEffect(() => {
    if (!isOpen || isReadOnly) setTitle(attrs[ECanvasAttributeNames.TITLE]);
  }, [attrs, isOpen, isReadOnly]);

  useEffect(() => {
    if (!decodedScene.ok || pendingSceneRef.current !== null) return;
    lastSavedSceneRef.current = decodedScene.value;
    lastSavedSceneFingerprintRef.current = getCanvasSceneFingerprint(decodedScene.value);
    if (lastSavedSceneEncodedRef.current !== attrs[ECanvasAttributeNames.SCENE]) {
      lastSavedSceneEncodedRef.current = attrs[ECanvasAttributeNames.SCENE];
      setExternalSceneRevision((revision) => revision + 1);
    }
  }, [attrs, decodedScene]);

  useEffect(() => {
    const updateTheme = () => setTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
    updateTheme();
    const observer = new MutationObserver(updateTheme);
    observer.observe(document.documentElement, { attributeFilter: ["class"], attributes: true });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const awareness = provider?.awareness;
    if (!awareness) return;
    const handleAwarenessChange = () => setRemoteEditor(readRemoteEditor(provider, canvasId));
    awareness.on("change", handleAwarenessChange);
    return () => awareness.off("change", handleAwarenessChange);
  }, [canvasId, provider]);

  const publishActiveCanvas = useCallback(
    (active: boolean) => {
      const awareness = provider?.awareness;
      if (!awareness) return;
      const current = awareness.getLocalState()?.planeCanvas as TCanvasAwarenessState | undefined;
      if (active) awareness.setLocalStateField("planeCanvas", { canvasId, userName });
      else if (current?.canvasId === canvasId) awareness.setLocalStateField("planeCanvas", null);
    },
    [canvasId, provider, userName]
  );

  const openCanvas = useCallback(() => {
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    setIsOpen(true);
    if (!isReadOnly) publishActiveCanvas(true);
  }, [isReadOnly, publishActiveCanvas]);

  useEffect(() => {
    const storage = editor.storage[CORE_EXTENSIONS.CANVAS] as { pendingOpenCanvasId?: string | null } | undefined;
    if (storage?.pendingOpenCanvasId === canvasId) {
      storage.pendingOpenCanvasId = null;
      openCanvas();
    }
    const handleOpen = (event: Event) => {
      const detail = (event as CustomEvent<{ canvasId?: string }>).detail;
      if (detail?.canvasId === canvasId) openCanvas();
    };
    window.addEventListener("plane:canvas-open", handleOpen);
    return () => window.removeEventListener("plane:canvas-open", handleOpen);
  }, [canvasId, editor.storage, openCanvas]);

  useEffect(() => () => publishActiveCanvas(false), [publishActiveCanvas]);

  useEffect(() => {
    if (!isOpen || !isEditable || isUnsupportedVersion) return;
    publishActiveCanvas(remoteEditor === null);
  }, [isEditable, isOpen, isUnsupportedVersion, publishActiveCanvas, remoteEditor]);

  const saveScene = useCallback(
    async (scene: TCanvasScene, revision: number): Promise<boolean> => {
      if (!isCurrentCanvasSaveRevision(revision, pendingSceneRevisionRef.current)) return true;
      setStatus("saving");
      const encoded = encodeCanvasScene(scene);
      if (!encoded.ok) {
        setStatus(getErrorStatus(encoded.code));
        return false;
      }
      try {
        const { renderCanvasPreview } = await import("./excalidraw-adapter");
        const width = Number(attrs[ECanvasAttributeNames.PREVIEW_WIDTH]);
        const height = Number(attrs[ECanvasAttributeNames.PREVIEW_HEIGHT]);
        const nextPreview = await renderCanvasPreview(scene, width, height);
        if (!isCurrentCanvasSaveRevision(revision, pendingSceneRevisionRef.current)) return true;
        const validPreview = validateCanvasPreview(nextPreview, width, height);
        if (!validPreview.ok) {
          setStatus(getErrorStatus(validPreview.code));
          return false;
        }
        const updated = editor.commands.updateCanvas(canvasId, {
          [ECanvasAttributeNames.TITLE]: normalizeCanvasTitle(title, t("canvas.untitled")),
          [ECanvasAttributeNames.SCENE_VERSION]: scene.version,
          [ECanvasAttributeNames.SCENE]: encoded.value,
          [ECanvasAttributeNames.PREVIEW]: validPreview.value,
        });
        if (!updated) throw new Error("Canvas transaction was rejected.");
        lastSavedSceneEncodedRef.current = encoded.value;
        lastSavedSceneRef.current = scene;
        lastSavedSceneFingerprintRef.current = getCanvasSceneFingerprint(scene);
        if (isCurrentCanvasSaveRevision(revision, pendingSceneRevisionRef.current)) {
          pendingSceneRef.current = null;
          pendingSceneFingerprintRef.current = null;
          setStatus("saved");
        }
        return true;
      } catch (error) {
        if (!isCurrentCanvasSaveRevision(revision, pendingSceneRevisionRef.current)) return true;
        console.error("Failed to save Canvas scene", error);
        setStatus("failed");
        return false;
      }
    },
    [attrs, canvasId, editor.commands, t, title]
  );

  const flushPendingSave = useCallback(async (): Promise<boolean> => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = null;
    if (!pendingSceneRef.current) return status !== "failed";
    return saveScene(pendingSceneRef.current, pendingSceneRevisionRef.current);
  }, [saveScene, status]);

  const handleSceneChange = useCallback(
    (scene: TCanvasScene) => {
      if (isReadOnly) return;
      const fingerprint = getCanvasSceneFingerprint(scene);
      const currentFingerprint = pendingSceneFingerprintRef.current ?? lastSavedSceneFingerprintRef.current;
      if (fingerprint === currentFingerprint) return;
      if (fingerprint === lastSavedSceneFingerprintRef.current) {
        if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
        pendingSceneRevisionRef.current += 1;
        pendingSceneRef.current = null;
        pendingSceneFingerprintRef.current = null;
        setStatus("saved");
        return;
      }
      pendingSceneRef.current = scene;
      pendingSceneFingerprintRef.current = fingerprint;
      const revision = pendingSceneRevisionRef.current + 1;
      pendingSceneRevisionRef.current = revision;
      setStatus("saving");
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(() => void saveScene(scene, revision), CANVAS_SAVE_DEBOUNCE_MS);
    },
    [isReadOnly, saveScene]
  );

  const closeCanvas = useCallback(async () => {
    const saved = await flushPendingSave();
    if (!saved) return;
    publishActiveCanvas(false);
    setIsOpen(false);
    requestAnimationFrame(() =>
      previouslyFocusedRef.current?.isConnected ? previouslyFocusedRef.current.focus() : editor.commands.focus()
    );
  }, [editor.commands, flushPendingSave, publishActiveCanvas]);

  const handleSizeChange = (size: TCanvasPreviewSize) => editor.commands.setCanvasPreviewSize(canvasId, size);
  const titleText = attrs[ECanvasAttributeNames.TITLE] || t("canvas.untitled");

  return (
    <NodeViewWrapper className="my-3" data-canvas-block="true" contentEditable={false}>
      <section
        className="mx-auto w-full overflow-hidden rounded-md border border-subtle bg-layer-1"
        style={{ maxWidth: `${Number(attrs[ECanvasAttributeNames.PREVIEW_WIDTH])}px` }}
        aria-label={t("canvas.aria.block", { title: titleText })}
      >
        <header className="flex min-h-10 items-center justify-between gap-2 border-b border-subtle px-3 py-2">
          <strong className="min-w-0 truncate text-13 font-medium text-primary">{titleText}</strong>
          <div className="flex shrink-0 items-center gap-1">
            {!isReadOnly && (
              <div
                className="hidden items-center rounded border border-subtle sm:flex"
                role="group"
                aria-label={t("canvas.aria.preview_size")}
              >
                {(["compact", "standard", "wide"] as const).map((size) => {
                  const Icon = size === "compact" ? Minimize2 : size === "standard" ? Expand : Maximize2;
                  return (
                    <button
                      key={size}
                      type="button"
                      className={cn("grid size-7 place-items-center text-secondary hover:bg-layer-1-hover", {
                        "bg-layer-1-active text-primary": displaySize === size,
                      })}
                      title={t(`canvas.size.${size}`)}
                      aria-label={t(`canvas.size.${size}`)}
                      aria-pressed={displaySize === size}
                      onClick={() => handleSizeChange(size)}
                    >
                      <Icon className="size-3.5" />
                    </button>
                  );
                })}
              </div>
            )}
            <button
              type="button"
              className="focus-visible:outline-accent-primary grid size-7 place-items-center rounded text-secondary hover:bg-layer-1-hover focus-visible:outline-2"
              title={t("canvas.action.open")}
              aria-label={t("canvas.action.open")}
              onClick={openCanvas}
            >
              <Maximize2 className="size-4" />
            </button>
          </div>
        </header>
        <button
          type="button"
          className="focus-visible:outline-accent-primary relative block w-full overflow-hidden text-left focus-visible:outline-2"
          style={{
            aspectRatio: `${attrs[ECanvasAttributeNames.PREVIEW_WIDTH]} / ${attrs[ECanvasAttributeNames.PREVIEW_HEIGHT]}`,
          }}
          onClick={openCanvas}
          aria-label={t("canvas.aria.open", { title: titleText })}
        >
          {shouldRenderCanvasPreview(preview, decodedScene.ok ? undefined : decodedScene.code) ? (
            <img className="size-full object-contain" src={preview} alt={titleText} />
          ) : (
            <span className="flex size-full min-h-40 flex-col items-center justify-center gap-2 p-4 text-center text-secondary">
              <AlertCircle className="size-5" />
              <span className="text-12">
                {isUnsupportedVersion ? t("canvas.error.unsupported_version") : t("canvas.preview_unavailable")}
              </span>
            </span>
          )}
        </button>
      </section>

      {isOpen && (
        <Dialog
          className="fixed inset-0 z-[1000] overflow-hidden"
          initialFocus={!decodedScene.ok || isReadOnly ? closeButtonRef : titleInputRef}
          onClose={() => void closeCanvas()}
          open
        >
          <Dialog.Panel
            className="flex size-full flex-col bg-surface-1"
            aria-label={t("canvas.aria.editor", { title: titleText })}
          >
            <header className="flex min-h-14 items-center gap-2 border-b border-subtle px-3 sm:px-4">
              <input
                ref={titleInputRef}
                className="focus-visible:ring-accent-primary min-w-0 flex-1 rounded-sm bg-transparent px-2 py-1 text-14 font-medium text-primary outline-none focus-visible:ring-2"
                value={title}
                readOnly={isReadOnly}
                maxLength={MAX_CANVAS_TITLE_LENGTH}
                aria-label={t("canvas.aria.title")}
                onChange={(event) => setTitle(event.target.value.slice(0, MAX_CANVAS_TITLE_LENGTH))}
                onBlur={() => {
                  if (!isReadOnly)
                    editor.commands.updateCanvas(canvasId, {
                      [ECanvasAttributeNames.TITLE]: normalizeCanvasTitle(title, t("canvas.untitled")),
                    });
                }}
              />
              <div className="flex items-center gap-2 text-12 text-secondary" aria-live="polite">
                {status === "saving" && <LoaderCircle className="size-4 animate-spin" />}
                {status !== "idle" && <span className="hidden sm:inline">{t(STATUS_KEYS[status])}</span>}
                {remoteEditor !== null && (
                  <span>{t("canvas.locked", { user: remoteEditor || t("canvas.collaborator") })}</span>
                )}
              </div>
              {!isReadOnly && (
                <>
                  <button
                    type="button"
                    className="grid size-8 place-items-center rounded hover:bg-layer-1-hover"
                    title={t("canvas.action.duplicate")}
                    aria-label={t("canvas.action.duplicate")}
                    onClick={() => editor.commands.duplicateCanvasBlock(canvasId)}
                  >
                    <Copy className="size-4" />
                  </button>
                  <button
                    type="button"
                    className="grid size-8 place-items-center rounded text-danger-primary hover:bg-layer-1-hover"
                    title={t("canvas.action.delete")}
                    aria-label={t("canvas.action.delete")}
                    onClick={() => {
                      publishActiveCanvas(false);
                      setIsOpen(false);
                      editor.commands.deleteCanvasBlock(canvasId);
                    }}
                  >
                    <Trash2 className="size-4" />
                  </button>
                </>
              )}
              <button
                ref={closeButtonRef}
                type="button"
                className="focus-visible:outline-accent-primary grid size-8 place-items-center rounded hover:bg-layer-1-hover focus-visible:outline-2"
                title={t("canvas.action.close")}
                aria-label={t("canvas.action.close")}
                onClick={() => void closeCanvas()}
              >
                <X className="size-5" />
              </button>
            </header>
            <main className="relative min-h-0 flex-1 overflow-hidden">
              {decodedScene.ok ? (
                <Suspense
                  fallback={
                    <div className="grid size-full place-items-center">
                      <LoaderCircle
                        className="size-6 animate-spin text-secondary"
                        aria-label={t("canvas.status.loading")}
                      />
                    </div>
                  }
                >
                  <LazyExcalidrawAdapter
                    key={`${canvasId}:${externalSceneRevision}`}
                    isReadOnly={isReadOnly}
                    onChange={handleSceneChange}
                    onInvalidChange={(code) => setStatus(getErrorStatus(code))}
                    scene={lastSavedSceneRef.current ?? decodedScene.value}
                    theme={theme}
                  />
                </Suspense>
              ) : (
                <div className="flex size-full flex-col items-center justify-center gap-3 p-6 text-center text-secondary">
                  <AlertCircle className="size-6" />
                  <p className="max-w-md text-13">
                    {decodedScene.code === "unsupported-version"
                      ? t("canvas.error.unsupported_version")
                      : t("canvas.preview_unavailable")}
                  </p>
                </div>
              )}
            </main>
          </Dialog.Panel>
        </Dialog>
      )}
    </NodeViewWrapper>
  );
}
