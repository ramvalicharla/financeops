module.exports = {
  extends: ["next/core-web-vitals"],
  rules: {
    "no-restricted-imports": [
      "error",
      {
        paths: [
          {
            name: "@/lib/api/accounting-journals",
            importNames: [
              "approveJournal",
              "postJournal",
              "reverseJournal",
              "submitJournal",
              "createJournal",
              "reviewJournal",
            ],
            message: "Use createGovernedIntent() instead of direct mutations.",
          },
        ],
      },
    ],
  },
}
