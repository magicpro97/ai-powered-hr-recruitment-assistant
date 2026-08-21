export type QuestionTypeLabels = {
  technical: string;
  behavioral: string;
  situational: string;
};

export function localizeInterviewQuestionType(
  type: string | undefined,
  labels: QuestionTypeLabels,
): string | undefined {
  const normalizedType = type?.trim();
  if (!normalizedType) return undefined;

  switch (normalizedType.toLowerCase()) {
    case "technical":
      return labels.technical;
    case "behavioral":
      return labels.behavioral;
    case "situational":
      return labels.situational;
    default:
      return normalizedType;
  }
}

export function localizeInterviewFocusArea(
  focusArea: string | undefined,
): string | undefined {
  const normalized = focusArea?.trim();
  if (!normalized) return undefined;
  const optimization = normalized.match(/^(.+?)\s+Optimization$/i);
  if (optimization) return `Tối ưu hóa ${optimization[1]}`;
  const troubleshooting = normalized.match(/^(.+?)\s*&\s*Troubleshooting$/i);
  if (troubleshooting) return `${troubleshooting[1]} & Xử lý sự cố`;
  if (
    /[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]/i.test(
      normalized,
    ) ||
    /^(?:Python|FastAPI|PostgreSQL|Docker|AWS|CI\/CD|REST API|SQL)$/i.test(
      normalized,
    )
  ) {
    return normalized;
  }
  return "Trọng tâm kỹ thuật";
}
