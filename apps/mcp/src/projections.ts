/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

type JsonRecord = Record<string, unknown>;

const asRecord = (value: unknown): JsonRecord => (value && typeof value === "object" ? (value as JsonRecord) : {});

const pick = (value: unknown, fields: readonly string[]): JsonRecord => {
  const source = asRecord(value);
  return Object.fromEntries(
    fields.filter((field) => source[field] !== undefined).map((field) => [field, source[field]])
  );
};

export const projectProjection = (value: unknown): JsonRecord =>
  pick(value, [
    "id",
    "name",
    "identifier",
    "description",
    "emoji",
    "icon_prop",
    "archived_at",
    "created_at",
    "updated_at",
  ]);

export const userProjection = (value: unknown): JsonRecord =>
  pick(value, ["id", "display_name", "first_name", "last_name", "avatar"]);

export const workItemProjection = (value: unknown): JsonRecord =>
  pick(value, [
    "id",
    "name",
    "sequence_id",
    "project_id",
    "state",
    "priority",
    "start_date",
    "target_date",
    "parent",
    "assignees",
    "labels",
    "cycle_id",
    "module_ids",
    "type_id",
    "created_at",
    "updated_at",
    "completed_at",
  ]);

export const commentProjection = (value: unknown): JsonRecord =>
  pick(value, ["id", "issue", "comment_html", "actor", "created_by", "access", "created_at", "updated_at"]);

export const stateProjection = (value: unknown): JsonRecord =>
  pick(value, ["id", "name", "description", "color", "group", "sequence"]);

export const labelProjection = (value: unknown): JsonRecord => pick(value, ["id", "name", "description", "color"]);

export const cycleProjection = (value: unknown): JsonRecord =>
  pick(value, ["id", "name", "description", "start_date", "end_date", "owned_by", "progress"]);

export const moduleProjection = (value: unknown): JsonRecord =>
  pick(value, ["id", "name", "description", "start_date", "target_date", "lead", "status"]);

export const memberProjection = (value: unknown): JsonRecord => {
  const source = asRecord(value);
  const member = source.member ?? source;
  return {
    ...pick(source, ["id", "role", "is_active"]),
    ...userProjection(member),
  };
};

const paginationFields = [
  "total_count",
  "next_cursor",
  "prev_cursor",
  "next_page_results",
  "prev_page_results",
  "count",
  "total_pages",
  "total_results",
] as const;

export const paginatedProjection = (
  value: unknown,
  projection: (entry: unknown) => JsonRecord,
  resultField = "results"
): { items: JsonRecord[]; pagination: JsonRecord } => {
  if (Array.isArray(value)) return { items: value.map(projection), pagination: { count: value.length } };
  const source = asRecord(value);
  const result = source[resultField];
  const items = Array.isArray(result) ? result.map(projection) : [];
  return { items, pagination: pick(source, paginationFields) };
};
