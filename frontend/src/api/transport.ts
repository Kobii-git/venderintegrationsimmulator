import { post } from "./client";
import type {
  HttpDeliveryResultResponse,
  HttpTransportRequest,
  SyslogTransportRequest,
} from "../types/api";

export function testHttpConnection(
  body: HttpTransportRequest,
): Promise<HttpDeliveryResultResponse> {
  return post<HttpDeliveryResultResponse>("/transport/http/test", body);
}

export function sendHttp(body: HttpTransportRequest): Promise<HttpDeliveryResultResponse> {
  return post<HttpDeliveryResultResponse>("/transport/http/send", body);
}

export function testSyslogConnection(
  body: SyslogTransportRequest,
): Promise<HttpDeliveryResultResponse> {
  return post<HttpDeliveryResultResponse>("/transport/syslog/test", body);
}

export function sendSyslog(body: SyslogTransportRequest): Promise<HttpDeliveryResultResponse> {
  return post<HttpDeliveryResultResponse>("/transport/syslog/send", body);
}
