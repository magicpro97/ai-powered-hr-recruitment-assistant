export default function JobsLoading() {
    return (
        <div className="max-w-6xl mx-auto animate-pulse">
            {/* Header skeleton */}
            <div className="mb-6">
                <div className="h-8 w-64 bg-gray-200 rounded-lg mb-3" />
                <div className="h-4 w-96 bg-gray-100 rounded-lg" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Left column - Form skeleton */}
                <div className="bg-white rounded-xl p-6 border border-gray-100">
                    <div className="h-6 w-48 bg-gray-200 rounded mb-6" />
                    <div className="space-y-4">
                        <div className="h-32 bg-gray-100 rounded-lg" />
                        <div className="h-12 bg-gray-200 rounded-lg" />
                    </div>
                </div>

                {/* Right column - Job list skeleton */}
                <div className="bg-white rounded-xl p-6 border border-gray-100">
                    <div className="h-6 w-40 bg-gray-200 rounded mb-6" />
                    <div className="space-y-4">
                        {[1, 2, 3].map((i) => (
                            <div
                                key={i}
                                className="p-4 bg-gray-50 rounded-lg border border-gray-100"
                            >
                                <div className="flex items-center gap-3 mb-3">
                                    <div className="w-10 h-10 bg-gray-200 rounded-lg" />
                                    <div className="flex-1">
                                        <div className="h-5 w-3/4 bg-gray-200 rounded mb-2" />
                                        <div className="h-4 w-1/2 bg-gray-100 rounded" />
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    <div className="h-6 w-20 bg-gray-100 rounded-full" />
                                    <div className="h-6 w-16 bg-gray-100 rounded-full" />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
