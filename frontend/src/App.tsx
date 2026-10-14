import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "next-themes";
import { AuthProvider } from "@/contexts/AuthContext";
import { I18nProvider } from "@/i18n";
import PageMeta from "@/components/PageMeta";
import OnboardingRedirect from "@/components/OnboardingRedirect";
import ErrorBoundary from "@/components/ErrorBoundary";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";

// Ana sayfa dışındaki sayfalar ayrı parçalar halinde, açıldıklarında
// yüklenir. Tek parça hâlinde ana sayfa ziyaretçisi haritayı (Leaflet),
// yönetim panelini ve sohbeti de indiriyordu: ~290 kB yerine ~190 kB
// (gzip). Google mobil yükleme hızını sıralamada kullanıyor; asıl kazanan da
// mobil veriyle giren öğrenci. Eski bir sekmedeki kopuk parça için bkz.
// main.tsx.
const Onboarding = lazy(() => import("./pages/Onboarding"));
const SwipeScreen = lazy(() => import("./pages/SwipeScreen"));
const Matches = lazy(() => import("./pages/Matches"));
const Messages = lazy(() => import("./pages/Messages"));
const ChatScreen = lazy(() => import("./pages/ChatScreen"));
const Profile = lazy(() => import("./pages/Profile"));
const ProfileEdit = lazy(() => import("./pages/ProfileEdit"));
const AccountSettings = lazy(() => import("./pages/AccountSettings"));
const CreateListing = lazy(() => import("./pages/CreateListing"));
const Listings = lazy(() => import("./pages/Listings"));
const Explore = lazy(() => import("./pages/Explore"));
const Safety = lazy(() => import("./pages/Safety"));
const Privacy = lazy(() => import("./pages/Privacy"));
const Login = lazy(() => import("./pages/Login"));
const Settings = lazy(() => import("./pages/Settings"));
const Admin = lazy(() => import("./pages/Admin"));

const queryClient = new QueryClient();

const App = () => (
  <ThemeProvider attribute="class" defaultTheme="light">
  <I18nProvider>
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          {/* Rota değişiminde sekme başlığını ve meta açıklamasını günceller. */}
          <PageMeta />
          <OnboardingRedirect />
          {/* Çizim hatası beyaz ekran yerine yenileme düğmeli bir sayfa
              gösterir; tembel yüklenen sayfanın parçası gelmezse de. */}
          <ErrorBoundary>
          <Suspense fallback={null}>
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/onboarding" element={<Onboarding />} />
            <Route path="/swipe" element={<SwipeScreen />} />
            {/* Eski "Bildirimler" sayfası Beğeniler'in kopyasıydı ve menüden
                erişilemiyordu; kaldırıldı. Yer imindeki adres boşa düşmesin. */}
            <Route path="/notifications" element={<Navigate to="/matches" replace />} />
            <Route path="/matches" element={<Matches />} />
            <Route path="/messages" element={<Messages />} />
            <Route path="/chat/:matchId" element={<ChatScreen />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/profile/edit" element={<ProfileEdit />} />
            <Route path="/create-listing" element={<CreateListing />} />
            <Route path="/listings" element={<Listings />} />
            <Route path="/explore" element={<Explore />} />
            <Route path="/safety" element={<Safety />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/login" element={<Login />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/settings/account" element={<AccountSettings />} />
            {/* Moderasyon paneli. Sayfa kendi içinde is_admin denetler ve
                yönetici olmayanı ana sayfaya gönderir; sunucu tarafında da
                tüm /api/admin/* uçları require_admin ile korunuyor. */}
            <Route path="/admin" element={<Admin />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
          </Suspense>
          </ErrorBoundary>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
  </I18nProvider>
  </ThemeProvider>
);

export default App;
