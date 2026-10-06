import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { UploadLogsPage } from "./pages/UploadLogsPage";
import { LogLabPage } from "./pages/LogLabPage";
import { Layout } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { DeliveryDetailPage } from "./pages/DeliveryDetailPage";
import { EventPreviewPage } from "./pages/EventPreviewPage";
import { InboundRequestDetailPage } from "./pages/InboundRequestDetailPage";
import { InboundRequestsPage } from "./pages/InboundRequestsPage";
import { SimulationFormPage } from "./pages/SimulationFormPage";
import { SimulationLivePage } from "./pages/SimulationLivePage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="uploads" element={<UploadLogsPage />} />
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
