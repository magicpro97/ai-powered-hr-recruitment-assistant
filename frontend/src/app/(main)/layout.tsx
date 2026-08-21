import ChatbotLoader from "@/components/ChatbotLoader";
import Sidebar from "@/components/Sidebar";

export default function MainLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <>
            {/* Skip to main content link for accessibility */}
            <a
                href="#main-content"
                className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-[#0369A1] focus:text-white focus:rounded-lg"
            >
                Skip to main content
            </a>
            <div className="flex min-h-[100dvh] bg-[#F8FAFC] overflow-x-hidden">
                <Sidebar />
                <main
                    id="main-content"
                    className="flex-1 min-w-0 px-3 pt-14 pb-4 sm:p-4 sm:pt-4 md:p-8 ml-0 md:ml-16 lg:ml-64 transition-all duration-300"
                    role="main"
                >
                    {children}
                </main>
            </div>
            <ChatbotLoader />
        </>
    );
}
