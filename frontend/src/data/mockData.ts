export interface UserProfile {
  id: string;
  name: string;
  gender: "erkek" | "kadın" | "belirtmek_istemiyorum";
  birthYear: number;
  university: string;
  department: string;
  year: number;
  budgetMin: number;
  budgetMax: number;
  smoking: boolean;
  pets: boolean;
  alcohol: boolean;
  sleepSchedule: "erken" | "gece" | "esnek";
  preferredDistrict: string;
  bio: string;
  photos: string[];
}

export interface Listing {
  id: string;
  userId: string;
  type: "ev_ilani" | "kisisel_ilan";
  title: string;
  description: string;
  rent?: number;
  budgetMin?: number;
  budgetMax?: number;
  district: string;
  roomCount?: string;
  smokingAllowed?: boolean;
  petsAllowed?: boolean;
  photos: string[];
  isActive: boolean;
  createdAt: string;
  user: UserProfile;
}

export const currentUser: UserProfile = {
  id: "user-me",
  name: "Ali Yılmaz",
  gender: "erkek",
  birthYear: 2002,
  university: "İTÜ",
  department: "Bilgisayar Mühendisliği",
  year: 3,
  budgetMin: 5000,
  budgetMax: 8000,
  smoking: false,
  pets: true,
  alcohol: false,
  sleepSchedule: "gece",
  preferredDistrict: "Kadıköy",
  bio: "Yazılımla ilgileniyorum, kedileri seviyorum. Temiz ve düzenli bir ev ortamı arıyorum.",
  photos: ["https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=400&fit=crop&crop=face"],
};

const mockUsers: UserProfile[] = [
  {
    id: "user-1",
    name: "Elif Demir",
    gender: "kadın",
    birthYear: 2001,
    university: "Boğaziçi Üniversitesi",
    department: "Psikoloji",
    year: 4,
    budgetMin: 6000,
    budgetMax: 9000,
    smoking: false,
    pets: true,
    alcohol: false,
    sleepSchedule: "erken",
    preferredDistrict: "Beşiktaş",
    bio: "Kitap kurdu, sabahçı biri. Sessiz ve huzurlu bir ev ortamı arıyorum.",
    photos: ["https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=400&h=400&fit=crop&crop=face"],
  },
  {
    id: "user-2",
    name: "Mehmet Kaya",
    gender: "erkek",
    birthYear: 2003,
    university: "İTÜ",
    department: "Elektrik Mühendisliği",
    year: 2,
    budgetMin: 4000,
    budgetMax: 6000,
    smoking: false,
    pets: false,
    alcohol: true,
    sleepSchedule: "gece",
    preferredDistrict: "Kadıköy",
    bio: "Müzikle ilgileniyorum, gitar çalıyorum. Eğlenceli ama saygılı bir ev arkadaşı arıyorum.",
    photos: ["https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=400&fit=crop&crop=face"],
  },
  {
    id: "user-3",
    name: "Zeynep Arslan",
    gender: "kadın",
    birthYear: 2002,
    university: "Marmara Üniversitesi",
    department: "Hukuk",
    year: 3,
    budgetMin: 5000,
    budgetMax: 7500,
    smoking: false,
    pets: false,
    alcohol: false,
    sleepSchedule: "erken",
    preferredDistrict: "Üsküdar",
    bio: "Staj dönemindeyim, sakin bir ev ortamı tercih ediyorum. Temizlik konusunda hassasım.",
    photos: ["https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=400&h=400&fit=crop&crop=face"],
  },
  {
    id: "user-4",
    name: "Can Öztürk",
    gender: "erkek",
    birthYear: 2001,
    university: "Yıldız Teknik Üniversitesi",
    department: "Mimarlık",
    year: 4,
    budgetMin: 5500,
    budgetMax: 8500,
    smoking: true,
    pets: true,
    alcohol: true,
    sleepSchedule: "esnek",
    preferredDistrict: "Beşiktaş",
    bio: "Mimarlık öğrencisi, yaratıcı projelerle uğraşıyorum. Kedim var, hayvan dostu ev arıyorum.",
    photos: ["https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=400&h=400&fit=crop&crop=face"],
  },
  {
    id: "user-5",
    name: "Selin Yıldırım",
    gender: "kadın",
    birthYear: 2003,
    university: "Sabancı Üniversitesi",
    department: "Ekonomi",
    year: 2,
    budgetMin: 7000,
    budgetMax: 10000,
    smoking: false,
    pets: false,
    alcohol: false,
    sleepSchedule: "esnek",
    preferredDistrict: "Kadıköy",
    bio: "Çalışkan ve düzenli biriyim. Yemek yapmayı seviyorum, mutfağı paylaşmak isterim.",
    photos: ["https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400&h=400&fit=crop&crop=face"],
  },
];

export const mockListings: Listing[] = [
  {
    id: "listing-1",
    userId: "user-1",
    type: "ev_ilani",
    title: "Beşiktaş'ta Deniz Manzaralı 2+1",
    description: "Beşiktaş merkeze 5 dk yürüme mesafesinde, deniz manzaralı ferah daire. Salon ve mutfak ortak, özel oda kilitli. Metro ve vapur durağına yakın.",
    rent: 7500,
    district: "Beşiktaş",
    roomCount: "2+1",
    smokingAllowed: false,
    petsAllowed: true,
    photos: ["/images/listing1.jpg"],
    isActive: true,
    createdAt: "2026-02-20T10:00:00Z",
    user: mockUsers[0],
  },
  {
    id: "listing-2",
    userId: "user-2",
    type: "kisisel_ilan",
    title: "Kadıköy'de Ev Arkadaşı Arıyorum",
    description: "Bütçem 4000-6000 TL arası, Kadıköy civarında ev arıyorum. Sessiz ve temiz bir ortam istiyorum. Erkek ev arkadaşı tercihim.",
    budgetMin: 4000,
    budgetMax: 6000,
    district: "Kadıköy",
    photos: ["https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=400&fit=crop&crop=face"],
    isActive: true,
    createdAt: "2026-02-21T14:00:00Z",
    user: mockUsers[1],
  },
  {
    id: "listing-3",
    userId: "user-3",
    type: "ev_ilani",
    title: "Üsküdar Merkez'de Geniş Oda",
    description: "Üsküdar merkezde, metroya 3 dk yürüme mesafesinde 3+1 dairede boş oda. Eşyalı, internet dahil. Temiz ve düzenli ev arkadaşı arıyoruz.",
    rent: 5500,
    district: "Üsküdar",
    roomCount: "3+1",
    smokingAllowed: false,
    petsAllowed: false,
    photos: ["/images/listing2.jpg"],
    isActive: true,
    createdAt: "2026-02-19T09:00:00Z",
    user: mockUsers[2],
  },
  {
    id: "listing-4",
    userId: "user-4",
    type: "ev_ilani",
    title: "Kadıköy Moda'da Balkonlu 2+1",
    description: "Moda sahiline 2 dk, balkonlu ferah daire. Ev arkadaşı olarak hayvan dostu, esnek saatlerde yaşayan biri tercih ediyorum.",
    rent: 8500,
    district: "Kadıköy",
    roomCount: "2+1",
    smokingAllowed: true,
    petsAllowed: true,
    photos: ["/images/listing3.jpg"],
    isActive: true,
    createdAt: "2026-02-22T16:00:00Z",
    user: mockUsers[3],
  },
  {
    id: "listing-5",
    userId: "user-5",
    type: "kisisel_ilan",
    title: "Kadıköy'de Kız Ev Arkadaşı Arıyorum",
    description: "Sabancı'da okuyorum, Kadıköy civarında birlikte ev tutacak kız ev arkadaşı arıyorum. Bütçem 7000-10000 TL arası.",
    budgetMin: 7000,
    budgetMax: 10000,
    district: "Kadıköy",
    photos: ["https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400&h=400&fit=crop&crop=face"],
    isActive: true,
    createdAt: "2026-02-23T11:00:00Z",
    user: mockUsers[4],
  },
  {
    id: "listing-6",
    userId: "user-1",
    type: "ev_ilani",
    title: "Beşiktaş Etiler'de Lüks Stüdyo",
    description: "Etiler'de tam eşyalı stüdyo daire. Güvenlikli site içinde, havuz ve spor salonu mevcut. Tek kişilik ideal.",
    rent: 12000,
    district: "Beşiktaş",
    roomCount: "1+0",
    smokingAllowed: false,
    petsAllowed: false,
    photos: ["/images/listing4.jpg"],
    isActive: true,
    createdAt: "2026-02-18T08:00:00Z",
    user: mockUsers[0],
  },
];

