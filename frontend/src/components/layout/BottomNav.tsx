import { Home, Heart, MessageCircle, User, Bell, Building2 } from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";

const navItems = [
  { icon: Home, label: "Keşfet", path: "/swipe" },
  { icon: Bell, label: "Bildirimler", path: "/notifications" },
  { icon: Heart, label: "Beğeniler", path: "/matches" },
  { icon: Building2, label: "Evler", path: "/listings" },
  { icon: MessageCircle, label: "Mesajlar", path: "/messages" },
  { icon: User, label: "Profil", path: "/profile" },
];

const BottomNav = () => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-card/80 backdrop-blur-lg" style={{ boxShadow: '0 -1px 0 rgba(0,0,0,0.04)' }}>
      <div className="max-w-lg mx-auto flex justify-around items-center pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] px-6">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path ||
            (item.path === "/messages" && location.pathname.startsWith("/chat"));
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={isActive ? "bottom-nav-item-active" : "bottom-nav-item"}
            >
              <item.icon className="w-6 h-6" strokeWidth={isActive ? 2.5 : 1.8} />
              <span className="text-[10px]">{item.label}</span>
              {isActive && (
                <div className="w-1 h-1 rounded-full bg-primary" />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
};

export default BottomNav;
