/**
 * Desk guard helpers. Permission-centric SoT is product-doors (CTR-PERM / D-002).
 * Do not add owner-name shortcuts or OWNER_ONLY_PATHS here.
 */

export {
  DESK_HOME_PERMISSION,
  canAccessDeskHome,
  getUserHome,
  hasPermission,
  isStaffUser,
} from "@/src/lib/product-doors";

export const DESK_CANDIDATE_HOME = "/app/matches";
export const DESK_RECRUITER_HOME = "/desk/sourcing-leads";
export const DESK_OWNER_HOME = "/desk";
