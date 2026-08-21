import Link from "next/link";

export default function NotFound() {
    return (
        <div className="flex items-center justify-center min-h-[60vh]">
            <div className="text-center">
                <h1 className="text-6xl font-bold text-gray-300">404</h1>
                <p className="text-lg text-gray-500 mt-4">
                    Trang không tồn tại hoặc bạn chưa đăng nhập
                </p>
                <Link
                    href="/login"
                    className="inline-block mt-6 px-6 py-2 bg-[#0369A1] text-white rounded-lg hover:bg-[#025a8a] transition-colors"
                >
                    Đăng nhập
                </Link>
            </div>
        </div>
    );
}
