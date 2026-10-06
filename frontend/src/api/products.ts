import { get, post } from "./client";
import type {
  ProductDetail,
  ProductSummary,
  ScenarioDetail,
  ScenarioEventRequest,
  ScenarioPreviewResponse,
  ScenarioSendRequest,
  ScenarioSendResponse,
  ScenarioSummary,
} from "../types/api";

export function listProducts(): Promise<ProductSummary[]> {
  return get<ProductSummary[]>("/products");
}

export function getProduct(productId: string): Promise<ProductDetail> {
  return get<ProductDetail>(`/products/${productId}`);
}

export function listScenarios(productId: string): Promise<ScenarioSummary[]> {
  return get<ScenarioSummary[]>(`/products/${productId}/scenarios`);
}

export function getScenario(productId: string, scenarioId: string): Promise<ScenarioDetail> {
  return get<ScenarioDetail>(`/products/${productId}/scenarios/${scenarioId}`);
}

export function previewScenario(
  productId: string,
  scenarioId: string,
  body: ScenarioEventRequest,
): Promise<ScenarioPreviewResponse> {
  return post<ScenarioPreviewResponse>(
    `/products/${productId}/scenarios/${scenarioId}/preview`,
    body,
  );
}

export function sendScenario(
  productId: string,
  scenarioId: string,
  body: ScenarioSendRequest,
): Promise<ScenarioSendResponse> {
  return post<ScenarioSendResponse>(`/products/${productId}/scenarios/${scenarioId}/send`, body);
}
