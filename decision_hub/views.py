import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST, require_http_methods

from .forms import ProjectForm, DecisionForm, AttachmentForm, UserProfileForm
from .models import Project, Decision, Category, Comment, Attachment, ActivityLog, FavoriteDecision
from .services import get_dashboard_stats, log_activity, seed_default_categories


@login_required(login_url="login")
def dashboard_view(request):
    """
    Main SaaS Dashboard view presenting executive metrics, risk charts, and recent activity.
    """
    seed_default_categories()
    stats = get_dashboard_stats(request.user)
    categories = Category.objects.all()

    return render(request, "decision_hub/dashboard.html", {
        "stats": stats,
        "categories": categories,
        "page_title": "Dashboard Overview"
    })


@login_required(login_url="login")
def projects_list_view(request):
    """
    Lists all workspace projects owned by the user and handles new project creation.
    """
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()

            log_activity(
                user=request.user,
                action_type="CREATE_PROJECT",
                description=f"Created project '{project.title}'",
                project=project
            )
            messages.success(request, f"Project '{project.title}' created successfully!")
            return redirect("decision_hub:project_detail", project_id=project.id)
    else:
        form = ProjectForm()

    projects = Project.objects.filter(owner=request.user)
    return render(request, "decision_hub/projects.html", {
        "projects": projects,
        "form": form,
        "page_title": "Projects Workspace"
    })


@login_required(login_url="login")
def project_create_page_view(request):
    """
    Dedicated page view for creating a new project workspace.
    """
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()

            log_activity(
                user=request.user,
                action_type="CREATE_PROJECT",
                description=f"Created project '{project.title}'",
                project=project
            )
            messages.success(request, f"Project '{project.title}' created successfully!")
            return redirect("decision_hub:project_detail", project_id=project.id)
    else:
        form = ProjectForm()

    return render(request, "decision_hub/project_create.html", {
        "form": form,
        "page_title": "Create New Project Workspace"
    })



@login_required(login_url="login")
def project_detail_view(request, project_id):
    """
    Project workspace page displaying decision cards, status filters, live search, and decision creation form.
    """
    project = get_object_or_404(Project, pk=project_id)
    if project.owner != request.user:
        return HttpResponseForbidden("You are not authorized to view this project.")

    decisions = project.decisions.all().select_related("category", "owner")
    categories = Category.objects.all()
    decision_form = DecisionForm()

    return render(request, "decision_hub/project_detail.html", {
        "project": project,
        "decisions": decisions,
        "categories": categories,
        "decision_form": decision_form,
        "page_title": f"Project: {project.title}"
    })


@login_required(login_url="login")
def project_edit_view(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    if project.owner != request.user:
        return HttpResponseForbidden("Permission denied.")

    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Project updated successfully.")
            return redirect("decision_hub:project_detail", project_id=project.id)
    else:
        form = ProjectForm(instance=project)

    return render(request, "decision_hub/project_edit.html", {
        "project": project,
        "form": form
    })


@login_required(login_url="login")
def project_delete_view(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    if project.owner != request.user:
        return HttpResponseForbidden("Permission denied.")

    if request.method == "POST":
        title = project.title
        project.delete()
        messages.success(request, f"Project '{title}' has been deleted.")
        return redirect("decision_hub:projects_list")

    return render(request, "decision_hub/project_delete_confirm.html", {"project": project})


@login_required(login_url="login")
def decision_create_view(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    if project.owner != request.user:
        return HttpResponseForbidden("Permission denied.")

    if request.method == "POST":
        form = DecisionForm(request.POST)
        if form.is_valid():
            decision = form.save(commit=False)
            decision.project = project
            decision.owner = request.user
            decision.save()

            log_activity(
                user=request.user,
                action_type="CREATE_DECISION",
                description=f"Created decision '{decision.title}' under project '{project.title}'",
                decision=decision,
                project=project
            )
            messages.success(request, f"Decision '{decision.title}' added successfully!")
            return redirect("decision_hub:decision_detail", decision_id=decision.id)
        else:
            messages.error(request, "Error creating decision. Please check form inputs.")
    else:
        form = DecisionForm()

    return render(request, "decision_hub/decision_create.html", {
        "project": project,
        "form": form,
        "page_title": f"Add New Decision to {project.title}"
    })



@login_required(login_url="login")
def decision_detail_view(request, decision_id):
    """
    Detailed decision hub page displaying full risk evaluation, category badges, comments stream, file attachments, and activity history.
    """
    decision = get_object_or_404(Decision, pk=decision_id)
    if decision.project.owner != request.user:
        return HttpResponseForbidden("You are not authorized to view this decision.")

    comments = decision.comments.all().select_related("author")
    attachments = decision.attachments.all().select_related("uploaded_by")
    activities = decision.activity_logs.all().select_related("user")[:15]
    attachment_form = AttachmentForm()

    is_favorite = decision.is_favorited_by(request.user)

    return render(request, "decision_hub/decision_detail.html", {
        "decision": decision,
        "comments": comments,
        "attachments": attachments,
        "activities": activities,
        "attachment_form": attachment_form,
        "is_favorite": is_favorite,
        "page_title": f"Decision: {decision.title}"
    })


@login_required(login_url="login")
def decision_edit_view(request, decision_id):
    decision = get_object_or_404(Decision, pk=decision_id)
    if decision.owner != request.user:
        return HttpResponseForbidden("Permission denied.")

    if request.method == "POST":
        form = DecisionForm(request.POST, instance=decision)
        if form.is_valid():
            form.save()
            log_activity(
                user=request.user,
                action_type="EDIT_DECISION",
                description=f"Updated decision '{decision.title}'",
                decision=decision,
                project=decision.project
            )
            messages.success(request, "Decision updated successfully.")
            return redirect("decision_hub:decision_detail", decision_id=decision.id)
    else:
        form = DecisionForm(instance=decision)

    return render(request, "decision_hub/decision_edit.html", {
        "decision": decision,
        "form": form
    })


@login_required(login_url="login")
def decision_delete_view(request, decision_id):
    decision = get_object_or_404(Decision, pk=decision_id)
    if decision.owner != request.user:
        return HttpResponseForbidden("Permission denied.")

    project_id = decision.project.id
    if request.method == "POST":
        title = decision.title
        log_activity(
            user=request.user,
            action_type="DELETE_DECISION",
            description=f"Deleted decision '{title}'",
            project=decision.project
        )
        decision.delete()
        messages.success(request, f"Decision '{title}' deleted.")
        return redirect("decision_hub:project_detail", project_id=project_id)

    return render(request, "decision_hub/decision_delete_confirm.html", {"decision": decision})


@login_required(login_url="login")
def favorites_view(request):
    """
    Displays grid of user's starred/bookmarked decisions.
    """
    favorites = FavoriteDecision.objects.filter(user=request.user).select_related("decision__project", "decision__category")
    return render(request, "decision_hub/favorites.html", {
        "favorites": favorites,
        "page_title": "Favorite Decisions"
    })


@login_required(login_url="login")
def activity_log_view(request):
    """
    Global activity timeline for workspace auditing.
    """
    activities_list = ActivityLog.objects.filter(user=request.user).select_related("decision", "project")
    paginator = Paginator(activities_list, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    return render(request, "decision_hub/activity.html", {
        "page_obj": page_obj,
        "page_title": "Activity Audit Log"
    })


@login_required(login_url="login")
def profile_view(request):
    """
    Displays user profile metadata, decision stats, and activity history.
    """
    user_projects_count = Project.objects.filter(owner=request.user).count()
    user_decisions_count = Decision.objects.filter(owner=request.user).count()
    user_favorites_count = FavoriteDecision.objects.filter(user=request.user).count()
    recent_activities = ActivityLog.objects.filter(user=request.user)[:10]

    return render(request, "decision_hub/profile.html", {
        "user_projects_count": user_projects_count,
        "user_decisions_count": user_decisions_count,
        "user_favorites_count": user_favorites_count,
        "recent_activities": recent_activities,
        "page_title": f"Profile: {request.user.username}"
    })


@login_required(login_url="login")
def edit_profile_view(request):
    """
    Edits user profile details.
    """
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("decision_hub:profile")
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, "decision_hub/edit_profile.html", {"form": form})


# ==========================================
# RESTful API Endpoints
# ==========================================

@login_required(login_url="login")
def api_decisions_list(request):
    """
    API Endpoint for live search and multi-parameter filtering of decisions.
    Supports params: q (text search), project_id, risk, priority, status, category.
    """
    decisions = Decision.objects.filter(owner=request.user).select_related("project", "category")

    q = request.GET.get("q", "").strip()
    project_id = request.GET.get("project_id", None)
    risk = request.GET.get("risk", None)
    priority = request.GET.get("priority", None)
    status = request.GET.get("status", None)
    category_id = request.GET.get("category", None)

    if q:
        decisions = decisions.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(category__name__icontains=q)
        )

    if project_id:
        decisions = decisions.filter(project_id=project_id)

    if risk:
        decisions = decisions.filter(risk_level=risk)

    if priority:
        decisions = decisions.filter(priority=priority)

    if status:
        decisions = decisions.filter(status=status)

    if category_id:
        decisions = decisions.filter(category_id=category_id)

    serialized = [d.serialize(request.user) for d in decisions]
    return JsonResponse({
        "count": len(serialized),
        "decisions": serialized
    })


@login_required(login_url="login")
@require_POST
def api_favorite_toggle(request, decision_id):
    """
    API endpoint for toggling favorite/star status on a decision.
    """
    decision = get_object_or_404(Decision, pk=decision_id)
    if decision.project.owner != request.user:
        return JsonResponse({"error": "Permission denied."}, status=403)

    fav_qs = FavoriteDecision.objects.filter(user=request.user, decision=decision)
    if fav_qs.exists():
        fav_qs.delete()
        is_favorite = False
    else:
        FavoriteDecision.objects.create(user=request.user, decision=decision)
        is_favorite = True
        log_activity(
            user=request.user,
            action_type="FAVORITE_TOGGLE",
            description=f"Starred decision '{decision.title}'",
            decision=decision,
            project=decision.project
        )

    return JsonResponse({"is_favorite": is_favorite})


@login_required(login_url="login")
@require_POST
def api_comment_add(request, decision_id):
    """
    API endpoint for posting a new comment on a decision without page reload.
    """
    decision = get_object_or_404(Decision, pk=decision_id)
    if decision.project.owner != request.user:
        return JsonResponse({"error": "Permission denied."}, status=403)

    try:
        data = json.loads(request.body)
        text = data.get("text", "").strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)

    if not text:
        return JsonResponse({"error": "Comment text cannot be empty."}, status=400)

    comment = Comment.objects.create(
        decision=decision,
        author=request.user,
        text=text
    )

    log_activity(
        user=request.user,
        action_type="ADD_COMMENT",
        description=f"Commented on decision '{decision.title}'",
        decision=decision,
        project=decision.project
    )

    return JsonResponse({
        "message": "Comment added successfully.",
        "comment": comment.serialize()
    }, status=201)


@login_required(login_url="login")
@require_POST
def api_attachment_upload(request, decision_id):
    """
    API endpoint for uploading file attachments (PDF/Images) to a decision.
    """
    decision = get_object_or_404(Decision, pk=decision_id)
    if decision.owner != request.user:
        return JsonResponse({"error": "Permission denied."}, status=403)

    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        attachment = form.save(commit=False)
        attachment.decision = decision
        attachment.uploaded_by = request.user
        attachment.filename = attachment.file.name.split("/")[-1]
        attachment.file_size = attachment.file.size
        attachment.save()

        log_activity(
            user=request.user,
            action_type="UPLOAD_ATTACHMENT",
            description=f"Uploaded file '{attachment.filename}' to decision '{decision.title}'",
            decision=decision,
            project=decision.project
        )

        messages.success(request, f"Attachment '{attachment.filename}' uploaded successfully!")
        return redirect("decision_hub:decision_detail", decision_id=decision.id)
    else:
        messages.error(request, "Invalid file format or upload error.")
        return redirect("decision_hub:decision_detail", decision_id=decision.id)
