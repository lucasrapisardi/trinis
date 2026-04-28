"use client";
export default function TourRestartButton() {
  function handleClick() {
    localStorage.removeItem("tour_dismissed");
    window.dispatchEvent(new CustomEvent("start-tour"));
  }
  return (
    <button
      onClick={handleClick}
      title="Replay tour"
      className="fixed bottom-5 right-5 w-8 h-8 rounded-full bg-brand-600 text-white text-sm font-bold flex items-center justify-center shadow-lg hover:bg-brand-700 z-50"
    >
      ?
    </button>
  );
}
