import type {
  JsonSchemaProperty,
  ObjectJsonSchema,
} from "../../types/api";

export type VendorOptionValue = string | number | boolean;

export function defaultsFromSchema(
  schema?: ObjectJsonSchema,
): Record<string, VendorOptionValue> {
  return Object.fromEntries(
    Object.entries(schema?.properties ?? {})
      .filter((entry): entry is [string, JsonSchemaProperty & { default: VendorOptionValue }] =>
        entry[1].default !== undefined
      )
      .map(([name, property]) => [name, property.default]),
  );
}
