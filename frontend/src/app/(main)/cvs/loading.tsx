export default function CVsLoading() {
    return (
        <div className="max-w-6xl mx-auto animate-pulse">
            {/* Header skeleton */}
            <div className="mb-6">
                <div className="h-8 w-56 bg-gray-200 rounded-lg mb-3" />
                <div className="h-4 w-80 bg-gray-100 rounded-lg" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Left column - Upload form skeleton */}
                <div className="bg-white rounded-xl p-6 border border-gray-100">
                    <div className="h-6 w-40 bg-gray-200 rounded mb-6" />

                    {/* Job selector skeleton */}
                    <div className="mb-6">
                        <div className="h-4 w-24 bg-gray-200 rounded mb-2" />
                        <div className="h-12 bg-gray-100 rounded-lg" />
                    </div>

                    {/* Upload area skeleton */}
                    <div className="h-40 border-2 border-dashed border-gray-200 rounded-lg flex items-center justify-center">
                        <div className="text-center">
                            <div className="w-12 h-12 bg-gray-200 rounded-full mx-auto mb-3" />
                            <div className="h-4 w-32 bg-gray-100 rounded mx-auto" />
                        </div>
                    </div>
                </div>

                {/* Right column - CV list skeleton */}
                <div className="bg-white rounded-xl p-6 border border-gray-100">
                    <div className="h-6 w-36 bg-gray-200 rounded mb-6" />
                    <div className="space-y-4">
                        {[1, 2, 3, 4].map((i) => (
                            <div
                                key={i}
                                className="p-4 bg-gray-50 rounded-lg border border-gray-100"
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-12 h-12 bg-gray-200 rounded-lg" />
                                    <div className="flex-1">
                                        <div className="h-5 w-40 bg-gray-200 rounded mb-2" />
                                        <div className="h-4 w-56 bg-gray-100 rounded" />
                                    </div>
                                    <div className="flex gap-2">
                                        <div className="w-8 h-8 bg-gray-100 rounded-lg" />
                                        <div className="w-8 h-8 bg-gray-100 rounded-lg" />
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
