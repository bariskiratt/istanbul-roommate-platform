/**
 * Kaydı yarıda kalmış hesabı (kod doğrulandı, profil hiç kaydedilmedi) kayda
 * geri gönderir.
 *
 * Böyle bir hesap e-postası doğrulandığı için oturum açabiliyor; eskiden
 * girişten sonra adı ve fotoğrafı olmayan bir profille desteye düşüyordu.
 * Login sayfası yarım hesabı zaten kayda yollar; bu bileşen, yenilenmiş bir
 * sekmeden ya da yer iminden doğrudan uygulama sayfasına gelinen durumu
 * kapatır.
 *
 * Yalnızca profil gerektiren sayfalar korunur. Ana sayfa, keşif, güvenlik ve
 * ayarlar (çıkış, hesap silme) açık kalır.
 */

import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/contexts/AuthContext";
import { profileIncomplete } from "@/lib/onboardingDraft";

const NEEDS_PROFILE = ["/swipe", "/matches", "/messages", "/chat/", "/profile", "/create-listing", "/edit-listing/"];

const OnboardingRedirect = () => {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (profileIncomplete(user) && NEEDS_PROFILE.some(p => pathname.startsWith(p))) {
      navigate("/onboarding", { replace: true });
    }
  }, [user, pathname, navigate]);

  return null;
};

export default OnboardingRedirect;
