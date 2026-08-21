"use client";

export default function Loading() {
    return (
        <div className="animate-pulse space-y-6">
            {/* Header skeleton */}
            <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-gray-200 rounded-xl"></div>
                <div className="space-y-2">
                    <div className="h-6 w-48 bg-gray-200 rounded"></div>
                    <div className="h-4 w-32 bg-gray-100 rounded"></div>
                </div>
            </div>

            {/* Stats skeleton */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="bg-white rounded-xl p-6 border border-gray-100">
                        <div className="h-4 w-24 bg-gray-200 rounded mb-2"></div>
                        <div className="h-8 w-16 bg-gray-100 rounded"></div>
                    </div>
                ))}
            </div>

            {/* Content skeleton */}
            <div className="bg-white rounded-xl p-6 border border-gray-100 space-y-4">
                <div className="h-5 w-40 bg-gray-200 rounded"></div>
                <div className="space-y-3">
                    {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="h-16 bg-gray-100 rounded-lg"></div>
                    ))}
                </div>
            </div>
        </div>
    );
}
