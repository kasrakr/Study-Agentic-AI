import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { Spinner } from "@/components/ui/feedback";

// Pages are loaded on demand so the Markdown renderer only ships with the chat page.
const Dashboard = lazy(() => import("@/pages/Dashboard"));
const StudyChat = lazy(() => import("@/pages/StudyChat"));
const Library = lazy(() => import("@/pages/Library"));
const Quiz = lazy(() => import("@/pages/Quiz"));
const Flashcards = lazy(() => import("@/pages/Flashcards"));

export default function App() {
  return (
    <Suspense fallback={<div className="p-8"><Spinner /></div>}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="chat" element={<StudyChat />} />
          <Route path="library" element={<Library />} />
          <Route path="quiz" element={<Quiz />} />
          <Route path="flashcards" element={<Flashcards />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
