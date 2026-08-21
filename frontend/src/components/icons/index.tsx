/**
 * Consolidated SVG Icons
 *
 * All icons in one place to avoid duplication across components.
 */

import { FC } from 'react';

interface IconProps {
    className?: string;
    filled?: boolean;
}

// Navigation & General
export const HomeIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3,12l2,-2m0,0l7,-7,7,7M5,10v10a1,1,0,001,1h3m10,-11l2,2m-2,-2v10a1,1,0,01,-1,1h-3m-6,0a1,1,0,001,-1v-4a1,1,0,011,-1h2a1,1,0,011,1v4a1,1,0,001,1m-6,0h6" />
    </svg>
);

export const SearchIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21,21l-6,-6m2,-5a7,7,0,11,-14,0,7,7,0,0114,0z" />
    </svg>
);

export const CheckIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5,13l4,4L19,7" />
    </svg>
);

export const CloseIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6,18L18,6M6,6l12,12" />
    </svg>
);

export const LockIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12,15v2m-6,4h12a2,2,0,002,-2v-6a2,2,0,00,-2,-2H6a2,2,0,00,-2,2v6a2,2,0,002,2zm10,-10V7a4,4,0,00,-8,0v4h8z" />
    </svg>
);

// Arrows & Navigation
export const ChevronDownIcon: FC<IconProps> = ({ className = "w-4 h-4" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19,9l-7,7,-7,-7" />
    </svg>
);

export const ChevronUpIcon: FC<IconProps> = ({ className = "w-4 h-4" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5,15l7,-7,7,7" />
    </svg>
);

export const ArrowRightIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17,8l4,4m0,0l-4,4m4,-4H3" />
    </svg>
);

// Documents & Files
export const DocumentIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9,12h6m-6,4h6m2,5H7a2,2,0,01,-2,-2V5a2,2,0,012,-2h5.586a1,1,0,01.707,.293l5.414,5.414a1,1,0,01.293,.707V19a2,2,0,01,-2,2z" />
    </svg>
);

export const FolderIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3,7v10a2,2,0,002,2h14a2,2,0,002,-2V9a2,2,0,00,-2,-2h-6l-2,-2H5a2,2,0,00,-2,2z" />
    </svg>
);

export const ClipboardIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9,5H7a2,2,0,00,-2,2v12a2,2,0,002,2h10a2,2,0,002,-2V7a2,2,0,00,-2,-2h-2M9,5a2,2,0,002,2h2a2,2,0,002,-2M9,5a2,2,0,012,-2h2a2,2,0,012,2" />
    </svg>
);

export const ClipboardListIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9,5H7a2,2,0,00,-2,2v12a2,2,0,002,2h10a2,2,0,002,-2V7a2,2,0,00,-2,-2h-2M9,5a2,2,0,002,2h2a2,2,0,002,-2M9,5a2,2,0,012,-2h2a2,2,0,012,2m-3,7h3m-3,4h3m-6,-4h.01M9,16h.01" />
    </svg>
);

// Users & People
export const UserIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16,7a4,4,0,11,-8,0,4,4,0,018,0zM12,14a7,7,0,00,-7,7h14a7,7,0,00,-7,-7z" />
    </svg>
);

export const UsersIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12,4.354a4,4,0,110,5.292M15,21H3v-1a6,6,0,0112,0v1zm0,0h6v-1a6,6,0,00,-9,-5.197M13,7a4,4,0,11,-8,0,4,4,0,018,0z" />
    </svg>
);

// Business & Work
export const BriefcaseIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21,13.255A23.931,23.931,0,0112,15c-3.183,0,-6.22,-.62,-9,-1.745M16,6V4a2,2,0,00,-2,-2h-4a2,2,0,00,-2,2v2m4,6h.01M5,20h14a2,2,0,002,-2V8a2,2,0,00,-2,-2H5a2,2,0,00,-2,2v10a2,2,0,002,2z" />
    </svg>
);

export const ChartIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9,19v-6a2,2,0,00,-2,-2H5a2,2,0,00,-2,2v6a2,2,0,002,2h2a2,2,0,002,-2zm0,0V9a2,2,0,012,-2h2a2,2,0,012,2v10m-6,0a2,2,0,002,2h2a2,2,0,002,-2m0,0V5a2,2,0,012,-2h2a2,2,0,012,2v14a2,2,0,01,-2,2h-2a2,2,0,01,-2,-2z" />
    </svg>
);

// Actions
export const UploadIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4,16v1a3,3,0,003,3h10a3,3,0,003,-3v-1m-4,-8l-4,-4m0,0L8,8m4,-4v12" />
    </svg>
);

export const TrashIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19,7l-.867,12.142A2,2,0,0116.138,21H7.862a2,2,0,01,-1.995,-1.858L5,7m5,4v6m4,-6v6m1,-10V4a1,1,0,00,-1,-1h-4a1,1,0,00,-1,1v3M4,7h16" />
    </svg>
);

export const DownloadIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4,16v1a3,3,0,003,3h10a3,3,0,003,-3v-1m-4,-4l-4,4m0,0l-4,-4m4,4V4" />
    </svg>
);

export const RefreshIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4,4v5h.582m15.356,2A8.001,8.001,0,004.582,9m0,0H9m11,11v-5h-.581m0,0a8.003,8.003,0,01,-15.357,-2m15.357,2H15" />
    </svg>
);

export const SendIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12,19l9,2,-9,-18,-9,18,9,-2zm0,0v-8" />
    </svg>
);

export const AttachIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172,7l-6.586,6.586a2,2,0,102.828,2.828l6.414,-6.586a4,4,0,00,-5.656,-5.656l-6.415,6.585a6,6,0,108.486,8.486L20.5,13" />
    </svg>
);

// AI & Special
export const SparklesIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5,3v4M3,5h4M6,17v4m-2,-2h4m5,-16l2.286,6.857L21,12l-5.714,2.143L13,21l-2.286,-6.857L5,12l5.714,-2.143L13,3z" />
    </svg>
);

export const BotIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75,17L9,20l-1,1h8l-1,-1,-.75,-3M3,13h18M5,17h14a2,2,0,002,-2V5a2,2,0,00,-2,-2H5a2,2,0,00,-2,2v10a2,2,0,002,2z" />
    </svg>
);

export const ChatIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8,12h.01M12,12h.01M16,12h.01M21,12c0,4.418,-4.03,8,-9,8a9.863,9.863,0,01,-4.255,-.949L3,20l1.395,-3.72C3.512,15.042,3,13.574,3,12c0,-4.418,4.03,-8,9,-8s9,3.582,9,8z" />
    </svg>
);

// Rating & Feedback
export const StarIcon: FC<IconProps> = ({ className = "w-4 h-4", filled = false }) => (
    <svg
        className={`${className} ${filled ? "text-[#F59E0B] fill-current" : "text-[#CBD5E1]"}`}
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        viewBox="0 0 24 24"
    >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049,2.927c.3,-.921,1.603,-.921,1.902,0l1.519,4.674a1,1,0,00.95,.69h4.915c.969,0,1.371,1.24,.588,1.81l-3.976,2.888a1,1,0,00,-.363,1.118l1.518,4.674c.3,.922,-.755,1.688,-1.538,1.118l-3.976,-2.888a1,1,0,00,-1.176,0l-3.976,2.888c-.783,.57,-1.838,-.197,-1.538,-1.118l1.518,-4.674a1,1,0,00,-.363,-1.118l-3.976,-2.888c-.784,-.57,-.38,-1.81,.588,-1.81h4.914a1,1,0,00.951,-.69l1.519,-4.674z" />
    </svg>
);

export const ThumbsUpIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14,10h4.764a2,2,0,011.789,2.894l-3.5,7A2,2,0,0115.263,21h-4.017c-.163,0,-.326,-.02,-.485,-.06L7,20m7,-10V5a2,2,0,00,-2,-2h-.095c-.5,0,-.905,.405,-.905,.905,0,.714,-.211,1.412,-.608,2.006L7,11v9m7,-10h-2M7,20H5a2,2,0,01,-2,-2v-6a2,2,0,012,-2h2.5" />
    </svg>
);

export const ThumbsDownIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10,14H5.236a2,2,0,01,-1.789,-2.894l3.5,-7A2,2,0,018.736,3h4.018a2,2,0,01.485,.06l3.76,.94m-7,10v5a2,2,0,002,2h.095c.5,0,.905,-.405,.905,-.905,0,-.714,.211,-1.412,.608,-2.006L17,13V4m-7,10h2m5,-10h2a2,2,0,012,2v6a2,2,0,01,-2,2h-2.5" />
    </svg>
);

// Info & Alerts
export const InfoIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13,16h-1v-4h-1m1,-4h.01M21,12a9,9,0,11,-18,0,9,9,0,0118,0z" />
    </svg>
);

export const ExclamationTriangleIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12,9v2m0,4h.01m-6.938,4h13.856c1.54,0,2.502,-1.667,1.732,-3L13.732,4c-.77,-1.333,-2.694,-1.333,-3.464,0L3.34,16c-.77,1.333,.192,3,1.732,3z" />
    </svg>
);

// Drag & Drop
export const DragHandleIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4,8h16M4,16h16" />
    </svg>
);

// Export all icons as a namespace for easy imports
// Expert & Calibration Icons
export const BadgeCheckIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9,12l2,2,4,-4M7.835,4.697a3.42,3.42,0,001.946,-.806,3.42,3.42,0,014.438,0,3.42,3.42,0,001.946,.806,3.42,3.42,0,013.138,3.138,3.42,3.42,0,00.806,1.946,3.42,3.42,0,010,4.438,3.42,3.42,0,00,-.806,1.946,3.42,3.42,0,01,-3.138,3.138,3.42,3.42,0,00,-1.946,.806,3.42,3.42,0,01,-4.438,0,3.42,3.42,0,00,-1.946,-.806,3.42,3.42,0,01,-3.138,-3.138,3.42,3.42,0,00,-.806,-1.946,3.42,3.42,0,010,-4.438,3.42,3.42,0,00.806,-1.946,3.42,3.42,0,013.138,-3.138z" />
    </svg>
);

export const ScaleIcon: FC<IconProps> = ({ className = "w-5 h-5" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3,6l3,1m0,0l-3,9a5.002,5.002,0,006.001,0M6,7l3,9M6,7l6,-2m6,2l3,-1m-3,1l-3,9a5.002,5.002,0,006.001,0M18,7l3,9m-3,-9l-6,-2m0,-2v2m0,16V5m0,16H9m3,0h3" />
    </svg>
);

export const Icons = {
    Home: HomeIcon,
    Search: SearchIcon,
    Check: CheckIcon,
    Close: CloseIcon,
    Lock: LockIcon,
    ChevronDown: ChevronDownIcon,
    ChevronUp: ChevronUpIcon,
    ArrowRight: ArrowRightIcon,
    Document: DocumentIcon,
    Folder: FolderIcon,
    Clipboard: ClipboardIcon,
    ClipboardList: ClipboardListIcon,
    User: UserIcon,
    Users: UsersIcon,
    Briefcase: BriefcaseIcon,
    Chart: ChartIcon,
    Upload: UploadIcon,
    Trash: TrashIcon,
    Refresh: RefreshIcon,
    Send: SendIcon,
    Attach: AttachIcon,
    Sparkles: SparklesIcon,
    Bot: BotIcon,
    Chat: ChatIcon,
    Star: StarIcon,
    ThumbsUp: ThumbsUpIcon,
    ThumbsDown: ThumbsDownIcon,
    DragHandle: DragHandleIcon,
    Info: InfoIcon,
    ExclamationTriangle: ExclamationTriangleIcon,
    BadgeCheck: BadgeCheckIcon,
    Scale: ScaleIcon,
};

export default Icons;
