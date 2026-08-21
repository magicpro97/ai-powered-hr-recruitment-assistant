export default function ScreeningLoading() {
    return (
        <div className="max-w-5xl mx-auto animate-pulse">
            {/* Header skeleton */}
            <div className="mb-6 flex items-center gap-3">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="flex items-center gap-2">
                        <div className="w-6 h-6 bg-gray-200 rounded-full" />
                        {i < 3 && <div className="flex-1 h-1 w-12 bg-gray-200 rounded" />}
                    </div>
                ))}
            </div>

            {/* Job selector skeleton */}
            <div className="bg-white rounded-xl p-6 border border-gray-100 mb-6">
                <div className="h-5 w-32 bg-gray-200 rounded mb-3" />
                <div className="h-12 bg-gray-100 rounded-lg" />
            </div>

            {/* Screen button skeleton */}
            <div className="h-12 w-full bg-gray-200 rounded-lg mb-8" />

            {/* Results skeleton */}
            <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                    <div
                        key={i}
                        className="bg-white rounded-xl p-6 border border-gray-100"
                    >
                        <div className="flex items-center gap-4 mb-4">
                            <div className="w-12 h-12 bg-gray-200 rounded-full" />
                            <div className="flex-1">
                                <div className="h-5 w-40 bg-gray-200 rounded mb-2" />
                                <div className="h-4 w-28 bg-gray-100 rounded" />
                            </div>
                            <div className="h-8 w-16 bg-gray-200 rounded-lg" />
                        </div>
                        <div className="h-2 bg-gray-100 rounded-full mb-3" />
                        <div className="flex gap-2">
                            {[1, 2, 3].map((j) => (
                                <div key={j} className="h-6 w-16 bg-gray-100 rounded-full" />
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
