export const translations = {
  en: {
    dashboardTitle: "CropSense AI dashboard",
    uploadPhoto: "Upload a leaf photo",
    analyze: "Analyze crop",
    analyzing: "Analyzing...",
    useLocation: "Use my location",
    askExpert: "Ask your farm expert",
    send: "Send",
    speak: "Read answer",
    voice: "Voice question",
    nav: {
      Dashboard: "Dashboard",
      Upload: "Upload",
      Results: "Results",
      Weather: "Weather",
      Chatbot: "Chatbot",
      Summary: "Summary",
      Admin: "Admin",
    },
  },
  te: {
    dashboardTitle: "క్రాప్‌సెన్స్ ఏఐ డ్యాష్‌బోర్డ్",
    uploadPhoto: "వరి ఆకు ఫోటోను అప్‌లోడ్ చేయండి",
    analyze: "పంటను విశ్లేషించండి",
    analyzing: "విశ్లేషిస్తోంది...",
    useLocation: "నా ప్రదేశాన్ని ఉపయోగించండి",
    askExpert: "వ్యవసాయ సహాయకుడిని అడగండి",
    send: "పంపండి",
    speak: "సమాధానం వినండి",
    voice: "వాయిస్ ప్రశ్న",
    nav: {
      Dashboard: "డ్యాష్‌బోర్డ్",
      Upload: "ఫోటో",
      Results: "ఫలితాలు",
      Weather: "వాతావరణం",
      Chatbot: "సహాయకుడు",
      Summary: "సారాంశం",
      Admin: "నిర్వాహకుడు",
    },
  },
};

export function translator(language) {
  const selected = translations[language] || translations.en;
  return (key) => key.split(".").reduce((value, part) => value?.[part], selected) || key;
}
