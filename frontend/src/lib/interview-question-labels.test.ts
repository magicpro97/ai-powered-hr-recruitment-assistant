import { describe, expect, test } from "bun:test";

import {
  localizeInterviewFocusArea,
  localizeInterviewQuestionType,
  type QuestionTypeLabels,
} from "./interview-question-labels";

const vietnameseLabels = {
  technical: "Kỹ thuật",
  behavioral: "Hành vi",
  situational: "Tình huống",
} satisfies QuestionTypeLabels;

const englishLabels = {
  technical: "Technical",
  behavioral: "Behavioral",
  situational: "Situational",
} satisfies QuestionTypeLabels;

describe("localizeInterviewQuestionType", () => {
  test.each([
    ["Technical", "Kỹ thuật"],
    ["technical", "Kỹ thuật"],
    ["  Technical  ", "Kỹ thuật"],
    ["\ttechnical\n", "Kỹ thuật"],
    ["Behavioral", "Hành vi"],
    ["Situational", "Tình huống"],
  ])("localizes known type %j", (type, expected) => {
    expect(localizeInterviewQuestionType(type, vietnameseLabels)).toBe(expected);
  });

  test("returns trimmed unknown types unchanged", () => {
    expect(localizeInterviewQuestionType("  General  ", vietnameseLabels)).toBe("General");
  });

  test.each([undefined, "", "   "])('returns undefined for %j', (type) => {
    expect(localizeInterviewQuestionType(type, vietnameseLabels)).toBeUndefined();
  });

  test("uses labels for the active language", () => {
    expect(localizeInterviewQuestionType("Technical", vietnameseLabels)).toBe("Kỹ thuật");
    expect(localizeInterviewQuestionType("Technical", englishLabels)).toBe("Technical");
  });
});

describe("localizeInterviewFocusArea", () => {
  test.each([
    ["Docker & Troubleshooting", "Docker & Xử lý sự cố"],
    ["PostgreSQL Optimization", "Tối ưu hóa PostgreSQL"],
    ["Python Optimization", "Tối ưu hóa Python"],
    ["Thiết kế hệ thống", "Thiết kế hệ thống"],
    ["Backend Architecture", "Trọng tâm kỹ thuật"],
  ])("localizes visible focus metadata %j", (focusArea, expected) => {
    expect(localizeInterviewFocusArea(focusArea)).toBe(expected);
  });
});
