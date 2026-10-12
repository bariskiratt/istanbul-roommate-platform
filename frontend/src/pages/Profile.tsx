import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Settings, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { motion } from "framer-motion";
import AuthGate from "@/components/AuthGate";
import { Button } from "@/components/ui/button";
import StudentCard from "@/components/campus/StudentCard";
import ProfileTimeline from "@/components/campus/ProfileTimeline";
import { useAuth } from "@/contexts/AuthContext";
import { fetchListings, fetchMatches, deleteListing } from "@/lib/api";
import { parseUtc } from "@/lib/date";
import { interleave, personPrompts } from "@/lib/prompts";
import { useI18n } from "@/i18n";

const Profile = () => {
  const { isLoggedIn, user: me } = useAuth();
  const navigate = useNavigate();
  const { t, n, locale } = useI18n();

  const { data: myListings = [] } = useQuery({
    queryKey: ["listings", "mine"],
    queryFn: () => fetchListings({ mine: true }),
    enabled: isLoggedIn && me !== null,
  });

  const { data: myMatches = [] } = useQuery({
    queryKey: ["matches"],
    queryFn: fetchMatches,
    enabled: isLoggedIn && me !== null,
  });

  const queryClient = useQueryClient();
  const removeListing = useMutation({
    mutationFn: deleteListing,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["listings"] });
      toast.success(t("profile.removed"));
    },
    onError: err =>
      toast.error(err instanceof Error ? err.message : t("profile.removeFailed")),
  });

  // İlan yayınlandıktan sonra doğrudan "İlanlarım" sekmesi açılır.
  const location = useLocation();
  const initialTab = (location.state as { tab?: string } | null)?.tab === "listings" ? "listings" : "photos";
  const [activeTab, setActiveTab] = useState<"photos" | "listings" | "about">(initialTab);

  // Kancalardan SONRA erken çıkışlar. Girişsizken AuthGate, oturum açıkken
  // `me` henüz gelmemişken yükleniyor durumu basılır: bu aralıkta sahte bir
  // profil göstermek kullanıcıya kendi bilgisiymiş gibi görünürdü.
  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-background pb-20">
        <AppHeader title={t("profile.title")} />
        <AuthGate show onClose={() => {}} />
        <BottomNav />
      </div>
    );
  }

  if (!me) {
    return (
      <div className="min-h-screen bg-background pb-20">
        <AppHeader title={t("profile.title")} />
        <p className="text-center text-sm text-muted-foreground py-16">{t("common.loading")}</p>
        <BottomNav />
      </div>
    );
  }

  const user = {
    name: me.name || t("messages.unnamed"),
    university: me.university ?? "—",
    department: me.department ?? "—",
    year: me.year ?? 0,
    preferredDistrict: me.preferred_districts.join(", ") || "—",
    budgetMin: me.budget_min ?? 0,
    budgetMax: me.budget_max ?? 0,
    smoking: me.smoking ?? false,
    pets: me.pets ?? false,
    alcohol: me.alcohol ?? false,
    sleepSchedule: (me.sleep_schedule ?? "esnek") as "erken" | "gece" | "esnek",
    bio: me.bio,
    photos: me.photos,
  };

  // Önizleme: başkalarının Beğeniler'de gördüğü düzen (kart, fotoğraf, kart…).
  // Kapak fotoğrafı yukarıdaki öğrenci kartında olduğu için 1'den başlar.
  const timeline = interleave(user.photos.slice(1), personPrompts(me, { t, n, locale }), 1);

  const matchCount = myMatches.length;
  const listingCount = myListings.length;
  const memberSince = parseUtc(me.created_at).toLocaleDateString(locale, {
    month: "short",
    year: "numeric",
  });

  return (
    <div className="min-h-screen bg-background pb-24">
      <AppHeader
        title={t("profile.title")}
        rightAction={
          <div className="flex items-center gap-1">
            <button
              onClick={() => navigate("/profile/edit")}
              className="h-10 px-3.5 rounded-full border border-border text-[13px] font-semibold text-foreground flex items-center gap-1.5 hover:bg-muted transition-colors"
            >
              <Pencil className="w-3.5 h-3.5" /> {t("profile.edit")}
            </button>
            <button
              onClick={() => navigate("/settings")}
              aria-label={t("settings.title")}
              className="w-10 h-10 rounded-full flex items-center justify-center text-foreground hover:bg-muted transition-colors"
            >
              <Settings className="w-5 h-5" />
            </button>
          </div>
        }
      />

      <div className="px-5 pt-5 max-w-lg mx-auto">
        {/* Öğrenci kartı: kişinin kendisi. Mühür yalnızca üniversite e-posta
            alan adından gelmişse basılır (bkz. StudentCard). */}
        <StudentCard
          name={user.name}
          photo={user.photos[0]}
          university={me.university}
          department={me.department}
          year={me.year}
          memberNo={me.id}
          verified={!!me.university}
        />

        <p className="mt-5 text-[14px] text-muted-foreground">
          <span className="font-semibold text-foreground">{listingCount}</span> {t("profile.statListings")}
          <span className="mx-2.5 text-border" aria-hidden="true">|</span>
          <span className="font-semibold text-foreground">{matchCount}</span> {t("profile.statMatches")}
          <span className="mx-2.5 text-border" aria-hidden="true">|</span>
          {t("profile.memberSince", { date: memberSince })}
        </p>

        {/* Sekmeler */}
        <div className="mt-6 flex border-b border-border" role="tablist">
          {[
            { key: "photos" as const, label: t("profile.tabPhotos") },
            { key: "listings" as const, label: t("profile.tabListings") },
            { key: "about" as const, label: t("profile.tabAbout") },
          ].map(tab => (
            <button
              key={tab.key}
              role="tab"
              aria-selected={activeTab === tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex-1 py-3 text-[14px] font-semibold transition-colors relative ${
                activeTab === tab.key ? "text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
              {activeTab === tab.key && (
                <motion.div layoutId="tab-underline" className="absolute -bottom-px left-0 right-0 h-[3px] bg-foreground" />
              )}
            </button>
          ))}
        </div>

        <div className="pt-4">
          {activeTab === "photos" && (
            <div className="space-y-3">
              <p className="text-[13px] text-muted-foreground">{t("profile.previewHint")}</p>
              {user.photos.length === 0 && (
                <div className="py-2 space-y-3">
                  <p className="text-muted-foreground">{t("profile.noPhotos")}</p>
                  <Button variant="outline" onClick={() => navigate("/profile/edit")}>{t("profile.edit")}</Button>
                </div>
              )}
              {timeline.length > 0 ? (
                <ProfileTimeline items={timeline} />
              ) : (
                user.photos.length > 0 && <p className="text-muted-foreground py-2">{t("profile.noPrompts")}</p>
              )}
              {/* Bio: kişinin kendi yazdığı metin, çizgili kâğıtta */}
              {user.bio && (
                <p className="paper-ruled rounded-lg text-[15px] text-foreground whitespace-pre-line">{user.bio}</p>
              )}
            </div>
          )}

          {activeTab === "listings" && (
            <div className="space-y-3">
              {myListings.length > 0 ? myListings.map(listing => (
                <div key={listing.id} className="rounded-2xl border border-border p-2 flex items-center gap-3">
                  {listing.photos[0] ? (
                    <img src={listing.photos[0]} alt="" className="w-20 h-20 rounded-xl object-cover shrink-0" />
                  ) : (
                    <div className="w-20 h-20 rounded-xl shrink-0 bg-muted" />
                  )}
                  <div className="flex-1 min-w-0 py-1">
                    <p className="text-[12px] text-muted-foreground">
                      {t(listing.type === "ev_ilani" ? "profile.house" : "profile.personal")}
                      {listing.is_active && <span className="ml-2 text-accent font-semibold">{t("profile.active")}</span>}
                    </p>
                    <p className="font-display text-[17px] leading-snug text-foreground truncate">{listing.title}</p>
                    <p className="text-[13px] text-muted-foreground">
                      {listing.district},{" "}
                      {listing.type === "ev_ilani"
                        ? `${n(listing.rent ?? 0)} TL`
                        : `${n(listing.budget_min ?? 0)}–${n(listing.budget_max ?? 0)} TL`}
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      if (window.confirm(t("profile.confirmRemove", { title: listing.title }))) {
                        removeListing.mutate(listing.id);
                      }
                    }}
                    disabled={removeListing.isPending}
                    aria-label={t("profile.removeListing")}
                    title={t("profile.removeListing")}
                    className="mr-1 w-10 h-10 shrink-0 rounded-full text-muted-foreground flex items-center justify-center hover:bg-destructive/10 hover:text-destructive transition-colors disabled:opacity-50"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              )) : (
                <p className="text-muted-foreground py-4">{t("profile.noListings")}</p>
              )}
              <Button variant="outline" onClick={() => navigate("/create-listing")} className="w-full h-12">
                <Plus /> {t("profile.newListing")}
              </Button>
            </div>
          )}

          {activeTab === "about" && (
            <dl className="divide-y divide-border">
              {[
                { label: t("profile.fieldEmail"), value: me?.email ?? "—" },
                { label: t("profile.fieldUniversity"), value: [me.university, me.department].filter(Boolean).join(", ") || "—" },
                { label: t("profile.fieldDistrict"), value: user.preferredDistrict },
                { label: t("profile.fieldBudget"), value: `${n(user.budgetMin)}–${n(user.budgetMax)} TL${t("common.perMonth")}` },
                { label: t("profile.fieldSmoking"), value: t(user.smoking ? "profile.smokes" : "profile.noSmoke") },
                { label: t("profile.fieldPets"), value: t(user.pets ? "profile.petFriendly" : "profile.noPets") },
                { label: t("profile.fieldAlcohol"), value: t(user.alcohol ? "profile.drinks" : "profile.noDrinks") },
                { label: t("profile.fieldSleep"), value: t(user.sleepSchedule === "gece" ? "profile.nightOwl" : user.sleepSchedule === "erken" ? "profile.earlyBird" : "profile.flexible") },
              ].map(field => (
                <div key={field.label} className="py-3 grid grid-cols-[8.5rem_1fr] gap-3">
                  <dt className="text-[13px] text-muted-foreground">{field.label}</dt>
                  <dd className="text-[15px] text-foreground break-words">{field.value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </div>

      <BottomNav />
    </div>
  );
};

export default Profile;
