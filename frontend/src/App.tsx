import { lazy } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";

const UploadLogsPage = lazy(() => import("./pages/UploadLogsPage").then((module) => ({ default: module.UploadLogsPage })));
const LogLabPage = lazy(() => import("./pages/LogLabPage").then((module) => ({ default: module.LogLabPage })));
const GuidesPage = lazy(() => import("./pages/GuidesPage").then((module) => ({ default: module.GuidesPage })));
const RawLogPage = lazy(() => import("./pages/RawLogPage").then((module) => ({ default: module.RawLogPage })));
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const DeliveryDetailPage = lazy(() => import("./pages/DeliveryDetailPage").then((module) => ({ default: module.DeliveryDetailPage })));
const EventPreviewPage = lazy(() => import("./pages/EventPreviewPage").then((module) => ({ default: module.EventPreviewPage })));
const InboundRequestDetailPage = lazy(() => import("./pages/InboundRequestDetailPage").then((module) => ({ default: module.InboundRequestDetailPage })));
const InboundRequestsPage = lazy(() => import("./pages/InboundRequestsPage").then((module) => ({ default: module.InboundRequestsPage })));
const SimulationFormPage = lazy(() => import("./pages/SimulationFormPage").then((module) => ({ default: module.SimulationFormPage })));
const SimulationLivePage = lazy(() => import("./pages/SimulationLivePage").then((module) => ({ default: module.SimulationLivePage })));

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="uploads" element={<UploadLogsPage />} />
          <Route path="guides" element={<GuidesPage />} />
          <Route path="guides/:productId/:methodId" element={<GuidesPage />} />
          <Route path="raw-logs" element={<RawLogPage />} />
          <Route path="lab" element={<LogLabPage />} />
          <Route path="lab/:id" element={<LogLabPage />} />
          <Route path="simulations/new" element={<SimulationFormPage />} />
          <Route path="inbound-requests" element={<InboundRequestsPage />} />
          <Route
            path="inbound-requests/:requestId"
            element={<InboundRequestDetailPage />}
          />
          <Route path="simulations/:id" element={<SimulationLivePage />} />
          <Route path="simulations/:id/edit" element={<SimulationFormPage />} />
          <Route
            path="simulations/:id/preview"
            element={<EventPreviewPage />}
          />
          <Route
            path="simulations/:id/events/:eventId"
            element={<DeliveryDetailPage />}
          />
          <Route
            path="simulations/:id/inbound-requests/:requestId"
            element={<InboundRequestDetailPage />}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
