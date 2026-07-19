# Feature Specification: Project Authorization

**Feature Branch**: `002-project-authorization`

**Created**: 2026-07-19

**Status**: Draft

**Input**: User description: "Autorización por proyecto: cada usuario puede crear sus propios proyectos y solo ve y opera sobre los proyectos a los que pertenece (membresía proyecto-usuario). Definir un modelo coherente de trabajo con proyectos: creación, propiedad, invitación de colaboradores y revocación de acceso, en lugar del modelo actual donde todo usuario autenticado ve todos los proyectos"

## The Working Model *(context)*

Every project is a private workspace. Whoever creates a project becomes its
owner; the owner invites the colleagues who need to work on that mine site
and removes them when they should no longer have access. A user's project
list is exactly the set of workspaces they belong to — nothing else on the
platform is visible to them, and nothing they do can touch a project they do
not belong to. Platform administrators keep an out-of-band administrative
channel for support cases, not a browsing UI.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Access limited to my projects (Priority: P1)

As a platform user (surveyor or engineer of a mining operation), I only see
and operate on the projects I am a member of. Projects of other teams do not
appear in my project list, and I cannot reach their surveys, processing
statuses, maps, 3D views, or downloads by any means — even if I know or
guess their identifiers.

**Why this priority**: This is the entire point of the feature. Today every
authenticated user sees every project; a single mis-shared account or a
curious user exposes all client sites at once. Nothing else in this feature
matters until this boundary exists.

**Independent Test**: Create two users and two projects with disjoint
membership. Verify each user sees exactly their own project in the list, and
that every project-scoped surface (survey list, upload, pending uploads,
processing status, retry, 2D map, 3D view, artifact downloads) of the other
project is inaccessible — indistinguishable from a project that does not
exist.

**Acceptance Scenarios**:

1. **Given** user A is a member of project P1 only and user B of project P2
   only, **When** each opens the project list, **Then** A sees only P1 and B
   sees only P2, each with its correct survey count.
2. **Given** user A knows the identifier of project P2 (or of one of its
   surveys), **When** A attempts to open it directly by address or requests
   any of its data, **Then** the platform responds exactly as if that project
   did not exist, revealing nothing about it.
3. **Given** user A is a member of P1, **When** A uploads, views progress,
   retries a failed run, or opens the 2D/3D viewers within P1, **Then**
   everything works as it does today — membership does not degrade any
   existing capability.
4. **Given** a survey inside P2 completed processing, **When** user A (not a
   member) tries to obtain its elevation surface, point cloud, or terrain
   shading, **Then** no content and no download addresses are handed out.

---

### User Story 2 - Create my own projects (Priority: P1)

As any platform user, I create projects for the mine sites I work on. The
project I create is mine: I become its owner, it appears immediately in my
list, and no other regular user can see it until I invite them.

**Why this priority**: Ownership at creation is the foundation the rest of
the model builds on — without a defined owner there is nobody who can invite
or revoke. It ships together with the P1 boundary.

**Independent Test**: A user creates a project and verifies they are its
owner, it appears in their list, and a second user cannot see it.

**Acceptance Scenarios**:

1. **Given** an authenticated user U, **When** U creates a project, **Then**
   U is recorded as its owner and the project appears in U's list with zero
   members other than U.
2. **Given** a freshly created project by U, **When** any other regular user
   opens their project list or tries the project's address, **Then** it is
   invisible and inaccessible to them.

---

### User Story 3 - Invite collaborators and revoke access (Priority: P2)

As a project owner, I manage who works with me from the project page: I add
teammates by their username and remove people who should no longer have
access. Every member can see who else has access; only owners can change the
list. Ownership itself can be shared or handed over.

**Why this priority**: Without self-service membership management, every
access change becomes an administrator intervention, which does not scale and
delays real work. It builds directly on the P1 boundary and ownership.

**Independent Test**: As a project owner, add a second user by username,
verify they gain access; remove them, verify their access ends. Verify a
non-owner member can see but not modify the member list.

**Acceptance Scenarios**:

1. **Given** owner O of project P and an existing user U who is not a member,
   **When** O adds U by username, **Then** P appears in U's project list and
   U can operate within it.
2. **Given** O types a username that does not exist, **When** the addition is
   submitted, **Then** a plain-language message explains the user was not
   found and the member list is unchanged.
3. **Given** member U (not owner) of project P, **When** U opens the member
   list, **Then** U sees all members and their roles but has no controls to
   add or remove anyone.
4. **Given** O removes member U, **When** U next interacts with the platform,
   **Then** P no longer appears in U's list and all of P's content is
   inaccessible to U, as in User Story 1.
5. **Given** project P has a single owner O, **When** O attempts to remove
   themselves or downgrade their ownership, **Then** the platform prevents it
   and explains that a project must always have at least one owner.
6. **Given** owner O of project P and member U, **When** O grants ownership
   to U, **Then** both are owners and either can manage the member list.

---

### User Story 4 - Existing projects survive the change (Priority: P3)

As a user who created projects before this feature existed, after the upgrade
I still see and operate on all my projects exactly as before, without any
manual step. Nobody loses access to work they created; nobody gains new
access they did not have a reason to hold.

**Why this priority**: The platform already holds real projects and surveys.
A migration that orphans projects or requires manual reassignment would turn
the security improvement into a data-loss incident.

**Independent Test**: With projects created before the upgrade, apply the
upgrade and verify each project's creator can list, open, and operate on
their project with no intervention, and that users who did not create a
project no longer see it.

**Acceptance Scenarios**:

1. **Given** a project created before the upgrade by user C, **When** the
   upgrade completes, **Then** C is its owner and retains full access.
2. **Given** users D who did not create that project, **When** they open
   their project list after the upgrade, **Then** the project is absent and
   its content inaccessible to them.

---

### Edge Cases

- Adding a user who is already a member: the platform reports it plainly and
  changes nothing.
- Removing a member who has an upload in progress on that project: the
  transfer of already-started file parts may finish in the background, but
  the removed user can no longer see the project, its pending uploads, or the
  resulting survey.
- Access revoked while the user is viewing a map or 3D scene: content links
  already handed to their browser keep working until they naturally expire
  (bounded, at most 60 minutes); every new request is denied.
- A user is deleted from the platform: their memberships disappear with them;
  projects where they were the sole owner must not become unmanageable —
  platform administrators can appoint a new owner through the existing
  administrative channel.
- Creating a project whose name collides with an invisible project: the
  platform keeps names unique across the whole installation, so the requester
  is told the name is taken even though they cannot see the other project.
  This minimal disclosure is accepted (see Assumptions).
- The automated processing pipeline itself (validation, reprojection, surface
  generation) is not a user and continues to operate on all projects
  regardless of membership.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project list MUST contain exactly the projects the
  requesting user is a member of — never any other project, in any state.
- **FR-002**: Every project-scoped capability — viewing surveys and their
  processing status, initiating and resuming uploads, listing pending
  uploads, retrying failed processing, opening 2D/3D visualizations, and
  obtaining any derived artifact — MUST be denied to non-members, and the
  denial MUST be indistinguishable from the project or survey not existing.
- **FR-003**: Any authenticated user MUST be able to create projects; the
  creator automatically becomes the project's owner at creation time.
- **FR-004**: Each membership MUST carry one of exactly two roles: owner
  (manages membership, plus everything a member can do) or member (full use
  of the project, no membership management).
- **FR-005**: Owners MUST be able to add an existing platform user as member
  or owner by exact username, remove members, and grant or revoke ownership,
  from the project page; attempts referencing unknown usernames MUST produce
  a plain-language error and change nothing.
- **FR-006**: A project MUST always have at least one owner; any operation
  that would leave it with none MUST be rejected with a comprehensible
  explanation.
- **FR-007**: All members of a project MUST be able to view its member list
  (username and role); only owners see management controls.
- **FR-008**: Access changes MUST take effect for all new requests
  immediately upon completion of the change; content links already issued
  remain valid only until their natural expiry, at most 60 minutes.
- **FR-009**: Each membership MUST record who granted it and when, and this
  MUST be visible in the member list.
- **FR-010**: Upon upgrade, every pre-existing project MUST end with its
  creator as owner, with no manual intervention and no other memberships
  created.
- **FR-011**: All user-visible texts introduced by this feature (member
  management, errors, confirmations) MUST exist in Spanish (primary) and
  English, consistent with the platform's language rules.
- **FR-012**: Server-to-server operations of the ingest pipeline (upload
  completion notifications, processing stages) MUST continue to work
  unchanged, as they act on behalf of the platform rather than a user.

### Key Entities

- **Project Membership**: The association between one platform user and one
  project. Attributes: role (owner or member), who granted it, when it was
  granted. A user has at most one membership per project. Removing the
  membership removes all of that user's access to the project.
- **Project** *(existing)*: Gains an owned member list; its creator is its
  first owner. All other attributes unchanged.
- **User** *(existing)*: Unchanged; participates in zero or more memberships.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A non-member exercising every user-facing surface of a project
  (list, direct addresses, statuses, maps, 3D, downloads, uploads) obtains
  zero information about it — verified for 100% of the surfaces in the
  feature's validation guide.
- **SC-002**: An access grant or revocation is reflected in the affected
  user's next interaction, within 5 seconds of the change.
- **SC-003**: 100% of projects existing before the upgrade remain fully
  usable by their creators immediately after it, with zero manual steps.
- **SC-004**: The project list and project pages load with no perceptible
  slowdown compared to before the feature (same load-time budget as the
  current success criteria, under identical data).
- **SC-005**: After a member is removed, any previously issued content link
  stops working within at most 60 minutes.
- **SC-006**: An owner can add a teammate and have them working inside the
  project in under 1 minute, without leaving the project page.

## Assumptions

- Two roles (owner/member) are sufficient for this feature. Finer-grained
  permissions (read-only viewers, per-capability roles) are a possible future
  feature and are out of scope.
- Platform administrators keep their existing administrative channel (command
  line / back office) with full reach, used for support cases such as
  re-assigning ownership of orphaned projects; no new administrator UI is
  part of this feature.
- Project names remain unique across the whole installation. The resulting
  minimal disclosure ("name already taken" for an invisible project) is
  accepted in exchange for operational simplicity — names are physical mine
  sites, and installations serve cooperating teams.
- Self-registration remains out of scope; accounts continue to be created
  administratively, so member addition can rely on exact usernames without a
  user search or invitation-by-email flow.
- There is no requirement to notify users when they are added to or removed
  from a project; they discover it in their project list. Notifications are
  out of scope.
- Content links already issued before a revocation expire on their own within
  their existing validity window (at most 60 minutes); immediate invalidation
  of outstanding links is out of scope.
