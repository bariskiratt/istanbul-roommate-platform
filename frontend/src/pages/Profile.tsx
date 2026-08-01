import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Settings, Edit, MapPin, GraduationCap, Calendar, DollarSign, Plus, Trash2, Instagram, Cigarette, Dog, Wine, Moon, FileText, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import LifestyleTag from "@/components/LifestyleTag";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { motion } from "framer-motion";
import AuthGate from "@/components/AuthGate";
import { useAuth } from "@/contexts/AuthContext";
import { fetchListings, fetchMatches, deleteListing } from "@/lib/api";
import { parseUtc } from "@/lib/date";
import { useI18n } from "@/i18n";

const placeholderAvatar = "https://api.dicebear.com/9.x/thumbs/svg?seed=roommatch-me";

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

  const [activeTab, setActiveTab] = useState<"photos" | "listings" | "about">("photos");
  const [bioExpanded, setBioExpanded] = useState(false);

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
    photos: me.photos.length > 0 ? me.photos : [placeholderAvatar],
  };

  const matchCount = myMatches.length;
  const listingCount = myListings.length;
  const memberSince = parseUtc(me.created_at).toLocaleDateString(locale, {
    month: "short",
    year: "numeric",
  });

  return (
    <div className="min-h-screen bg-background pb-20">
      <AppHeader
        title={t("profile.title")}
        rightAction={
          <div className="flex items-center gap-2">
            {me && (
              <button onClick={() => navigate("/profile/edit")} className="text-xs font-medium text-primary flex items-center gap-1 px-3 py-2 rounded-full hover:bg-primary/5 transition-colors">
                {t("profile.edit")} <Edit className="w-3 h-3" />
              </button>
            )}
            <button onClick={() => navigate("/settings")} className="w-10 h-10 rounded-full bg-card flex items-center justify-center text-muted-foreground hover:bg-muted transition-colors" style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <Settings className="w-5 h-5" />
            </button>
          </div>
        }
      />

      {/* Compact hero — max 200px */}
      <div className="relative" style={{ maxHeight: 200 }}>
        <div className="h-[100px]" style={{ background: "linear-gradient(135deg, hsl(var(--lavender)) 0%, hsl(var(--background)) 100%)" }} />
        
        <div className="px-6 -mt-10 relative z-10">
          <div className="flex items-start gap-4">
            {/* Avatar */}
            <div className="relative flex-shrink-0">
              <img
                src={user.photos[0]}
                alt={user.name}
                className="w-20 h-20 rounded-full object-cover object-top border-4 border-card shadow-lg"
              />
            </div>
            {/* Info right of avatar */}
            <div className="flex-1 pt-2">
              <h2 className="text-xl font-bold text-foreground">{user.name}</h2>
              <p className="text-xs text-muted-foreground mt-0.5">{user.university} · {user.department}</p>
              <p className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-1">
                <MapPin className="w-3 h-3" /> {user.preferredDistrict} · {t("likes.year", { year: user.year })}
              </p>
              {/* Budget pill */}
              <div className="mt-2 inline-flex items-center gap-1.5 bg-accent/15 rounded-full px-3 py-1">
                <DollarSign className="w-3 h-3 text-accent" />
                <span className="text-xs font-bold text-foreground">
                  {n(user.budgetMin)} — {n(user.budgetMax)} ₺
                </span>
              </div>
            </div>
          </div>

          {/* Lifestyle tags */}
          <div className="flex flex-wrap gap-1.5 mt-3">
            <LifestyleTag type="smoking" value={user.smoking} />
            <LifestyleTag type="pets" value={user.pets} />
            <LifestyleTag type="alcohol" value={user.alcohol} />
            <LifestyleTag type="sleep" value={user.sleepSchedule} />
          </div>
        </div>
      </div>

      {/* Bio */}
      <div className="px-6 pt-4">
        {user.bio && (
          <div>
            <p className={`text-sm text-muted-foreground italic leading-relaxed ${!bioExpanded ? "line-clamp-3" : ""}`}>
              "{user.bio}"
            </p>
            {user.bio.length > 120 && (
              <button onClick={() => setBioExpanded(!bioExpanded)} className="text-xs text-primary font-medium mt-1">
                {t(bioExpanded ? "profile.showLess" : "profile.showMore")}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Stats row */}
      <div className="px-6 pt-4">
        <div className="grid grid-cols-3 border border-border rounded-xl overflow-hidden">
          {[
            { label: t("profile.statListings"), value: listingCount.toString() },
            { label: t("profile.statMatches"), value: matchCount.toString() },
            { label: t("profile.statMember"), value: memberSince },
          ].map((stat, i) => (
            <div key={stat.label} className={`text-center py-3 ${i < 2 ? "border-r border-border" : ""}`}>
              <p className="text-lg font-bold text-foreground">{stat.value}</p>
              <p className="text-[11px] text-muted-foreground">{stat.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Tab bar */}
      <div className="px-6 pt-5">
        <div className="flex border-b border-border">
          {[
            { key: "photos" as const, label: t("profile.tabPhotos") },
            { key: "listings" as const, label: t("profile.tabListings") },
            { key: "about" as const, label: t("profile.tabAbout") },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex-1 py-3 text-sm font-medium transition-colors relative ${
                activeTab === tab.key ? "text-primary" : "text-muted-foreground"
              }`}
            >
              {tab.label}
              {activeTab === tab.key && (
                <motion.div
                  layoutId="tab-underline"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full"
                />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="px-6 pt-4">
        {activeTab === "photos" && (
          user.photos.length > 0 ? (
            <div className="grid grid-cols-3 gap-2">
              {user.photos.map((photo, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: i * 0.05 }}
                  className="aspect-square rounded-lg overflow-hidden"
                >
                  <img src={photo} alt="" className="w-full h-full object-cover object-top" />
                </motion.div>
              ))}
            </div>
          ) : (
            <p className="text-center text-sm text-muted-foreground py-8">{t("profile.noPhotos")}</p>
          )
        )}

        {activeTab === "listings" && (
          <div className="space-y-3">
            {myListings.length > 0 ? myListings.map((listing, i) => (
              <motion.div
                key={listing.id}
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: i * 0.1 }}
                className="card-listing overflow-hidden flex"
              >
                <img src={listing.photos[0] ?? placeholderAvatar} alt="" className="w-28 h-28 object-cover" />
                <div className="p-4 flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] px-2.5 py-1 rounded-full font-medium ${
                      listing.type === "ev_ilani" ? "bg-lavender/50 text-foreground" : "bg-accent/15 text-foreground"
                    }`}>
                      {t(listing.type === "ev_ilani" ? "profile.house" : "profile.personal")}
                    </span>
                    {listing.is_active && (
                      <span className="text-[10px] px-2.5 py-1 rounded-full bg-accent/15 text-foreground font-medium">{t("profile.active")}</span>
                    )}
                  </div>
                  <p className="font-bold text-sm text-foreground mt-1.5 truncate">{listing.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {listing.district} • {listing.type === "ev_ilani"
                      ? `${n(listing.rent ?? 0)} ₺`
                      : `${n(listing.budget_min ?? 0)}–${n(listing.budget_max ?? 0)} ₺`}
                  </p>
                </div>
                <button
                  onClick={() => {
                    if (window.confirm(t("profile.confirmRemove", { title: listing.title }))) {
                      removeListing.mutate(listing.id);
                    }
                  }}
                  disabled={removeListing.isPending}
                  className="self-center mr-3 w-9 h-9 rounded-full bg-destructive/10 text-destructive flex items-center justify-center hover:bg-destructive hover:text-destructive-foreground transition-colors disabled:opacity-50"
                  title={t("profile.removeListing")}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </motion.div>
            )) : (
              <p className="text-center text-muted-foreground py-8">{t("profile.noListings")}</p>
            )}
            <motion.button
              whileTap={{ scale: 0.98 }}
              onClick={() => navigate("/create-listing")}
              className="w-full card-listing p-4 flex items-center justify-center gap-2 text-primary font-semibold hover:shadow-lg transition-shadow"
            >
              <Plus className="w-5 h-5" />
              {t("profile.newListing")}
            </motion.button>
          </div>
        )}

        {activeTab === "about" && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-0"
          >
            {[
              { icon: "✉️", label: t("profile.fieldEmail"), value: me?.email ?? "—" },
              { icon: "🎓", label: t("profile.fieldUniversity"), value: `${user.university} · ${user.department}` },
              { icon: "📍", label: t("profile.fieldDistrict"), value: user.preferredDistrict },
              { icon: "💰", label: t("profile.fieldBudget"), value: `${n(user.budgetMin)} — ${n(user.budgetMax)} ₺${t("common.perMonth")}` },
              { icon: "🚬", label: t("profile.fieldSmoking"), value: t(user.smoking ? "profile.smokes" : "profile.noSmoke") },
              { icon: "🐾", label: t("profile.fieldPets"), value: t(user.pets ? "profile.petFriendly" : "profile.noPets") },
              { icon: "🍺", label: t("profile.fieldAlcohol"), value: t(user.alcohol ? "profile.drinks" : "profile.noDrinks") },
              { icon: "🌙", label: t("profile.fieldSleep"), value: t(user.sleepSchedule === "gece" ? "profile.nightOwl" : user.sleepSchedule === "erken" ? "profile.earlyBird" : "profile.flexible") },
              { icon: "📝", label: t("profile.fieldBio"), value: user.bio },
            ].map((field, i) => (
              <div key={field.label} className="flex items-start gap-3 py-3 border-b border-border last:border-0">
                <span className="text-base">{field.icon}</span>
                <div className="flex-1">
                  <p className="text-xs text-muted-foreground">{field.label}</p>
                  <p className="text-sm text-foreground mt-0.5">{field.value}</p>
                </div>
              </div>
            ))}
          </motion.div>
        )}
      </div>

      <BottomNav />
    </div>
  );
};

export default Profile;
