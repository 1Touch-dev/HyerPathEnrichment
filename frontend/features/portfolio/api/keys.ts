export const portfolioKeys = {
  all: ["portfolio"] as const,
  profile: () => [...portfolioKeys.all, "profile"] as const,
  public: (slug: string) => [...portfolioKeys.all, "public", slug] as const,
};
