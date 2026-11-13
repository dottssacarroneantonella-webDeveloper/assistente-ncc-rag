import { Navigate, Route, Routes } from "react-router";
import { AdminLayout } from "./admin/AdminLayout";
import { AuthProvider } from "./admin/AuthContext";
import { ConversationDetailPage } from "./admin/ConversationDetailPage";
import { ConversationsPage } from "./admin/ConversationsPage";
import { DocumentsPage } from "./admin/DocumentsPage";
import { LoginPage } from "./admin/LoginPage";
import { UnansweredPage } from "./admin/UnansweredPage";
import { ChatPage } from "./pages/ChatPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<ChatPage />} />
      <Route
        path="/admin/*"
        element={
          <AuthProvider>
            <Routes>
              <Route path="login" element={<LoginPage />} />
              <Route element={<AdminLayout />}>
                <Route index element={<Navigate to="documenti" replace />} />
                <Route path="documenti" element={<DocumentsPage />} />
                <Route path="conversazioni" element={<ConversationsPage />} />
                <Route path="conversazioni/:id" element={<ConversationDetailPage />} />
                <Route path="domande" element={<UnansweredPage />} />
              </Route>
            </Routes>
          </AuthProvider>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
